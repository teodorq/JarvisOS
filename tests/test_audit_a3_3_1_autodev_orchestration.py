from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
)
from app.ai.autonomous_dev_orchestration_service import (
    AutonomousDevOrchestrationService,
)


class AuditA331AutoDevOrchestrationTests(
    unittest.TestCase
):

    def setUp(self) -> None:
        self.project_root = Path(
            __file__
        ).resolve().parents[1]

    def test_controller_is_reduced_below_two_thousand_lines(
        self,
    ) -> None:
        source = (
            self.project_root
            / "app/ai/autonomous_dev_controller.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertLess(
            len(source.splitlines()),
            2000,
        )

    def test_public_methods_remain_thin_wrappers(
        self,
    ) -> None:
        source = (
            self.project_root
            / "app/ai/autonomous_dev_controller.py"
        ).read_text(
            encoding="utf-8",
        )
        tree = ast.parse(source)
        controller_class = next(
            node
            for node in tree.body
            if isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "AutonomousDevController"
        )
        methods = {
            node.name: node
            for node in controller_class.body
            if isinstance(
                node,
                ast.FunctionDef,
            )
        }

        for name in (
            "handle",
            "run_autonomous_loop",
            "run_generation_cycle",
        ):
            self.assertIn(
                name,
                methods,
            )
            self.assertLessEqual(
                methods[name].end_lineno
                - methods[name].lineno
                + 1,
                20,
            )

    def test_service_is_stateless(self) -> None:
        self.assertEqual(
            vars(
                AutonomousDevOrchestrationService()
            ),
            {},
        )

    def test_empty_command_behavior_is_preserved(
        self,
    ) -> None:
        controller = (
            AutonomousDevController.__new__(
                AutonomousDevController
            )
        )

        result = controller.handle("")

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "EMPTY_COMMAND",
        )

    def test_status_command_behavior_is_preserved(
        self,
    ) -> None:
        controller = (
            AutonomousDevController.__new__(
                AutonomousDevController
            )
        )
        controller.pipeline = MagicMock()
        controller.pipeline.status.return_value = {
            "state": "running",
        }
        controller.backlog_summary = MagicMock(
            return_value={
                "total": 2,
            }
        )
        controller.planner = MagicMock()
        controller.planner.status.return_value = {
            "state": "ready",
        }
        controller.last_planning_cycle = None
        controller.last_generation_cycle = None

        result = controller.handle(
            "autonomous dev status"
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "STATUS",
        )
        self.assertEqual(
            result["backlog"]["total"],
            2,
        )

    def test_generation_cycle_fallback_is_preserved(
        self,
    ) -> None:
        controller = (
            AutonomousDevController.__new__(
                AutonomousDevController
            )
        )
        controller.last_planning_cycle = None
        controller.last_generation_cycle = None
        controller.run_planning_cycle = MagicMock(
            return_value={
                "success": True,
                "status": "NO_TASKS",
            }
        )

        result = controller.run_generation_cycle()

        self.assertEqual(
            result["status"],
            "NO_TASKS",
        )
        self.assertEqual(
            controller.last_generation_cycle[
                "status"
            ],
            "NO_TASKS",
        )

    def test_autonomous_loop_no_tasks_behavior_is_preserved(
        self,
    ) -> None:
        controller = (
            AutonomousDevController.__new__(
                AutonomousDevController
            )
        )
        controller.policy = SimpleNamespace(
            auto_approve=False,
            auto_execute=True,
            auto_start_pipeline=False,
        )
        controller.pipeline = MagicMock()
        controller.pipeline.status.return_value = {
            "state": "stopped",
        }
        controller.run_generation_cycle = MagicMock(
            return_value={
                "success": True,
                "status": "NO_TASKS",
            }
        )
        controller.backlog_summary = MagicMock(
            return_value={
                "total": 0,
            }
        )
        controller._remember_learning = MagicMock()
        controller._safe_positive_int = MagicMock(
            return_value=1,
        )
        controller.last_planning_cycle = None
        controller.last_generation_cycle = None
        controller.last_autonomous_loop = None

        result = controller.run_autonomous_loop(
            max_cycles=1
        )

        self.assertEqual(
            result["status"],
            "NO_TASKS",
        )
        self.assertTrue(
            result["success"]
        )
        controller._remember_learning.assert_called_once()


if __name__ == "__main__":
    unittest.main()

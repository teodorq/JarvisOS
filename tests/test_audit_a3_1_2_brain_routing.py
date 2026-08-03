from __future__ import annotations

import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from app.ai.brain import Brain
from app.ai.brain_command_router import (
    BrainCommandRouter,
)


class AuditA312BrainRoutingTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(
            __file__
        ).resolve().parents[1]

    def test_brain_is_reduced_below_one_thousand_lines(self) -> None:
        source = (
            self.project_root
            / "app/ai/brain.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertLess(
            len(source.splitlines()),
            1000,
        )

    def test_brain_keeps_think_and_execute_wrappers(self) -> None:
        source = (
            self.project_root
            / "app/ai/brain.py"
        ).read_text(
            encoding="utf-8",
        )
        tree = ast.parse(source)
        brain_class = next(
            node
            for node in tree.body
            if isinstance(
                node,
                ast.ClassDef,
            )
            and node.name == "Brain"
        )
        methods = {
            node.name: node
            for node in brain_class.body
            if isinstance(
                node,
                ast.FunctionDef,
            )
        }

        self.assertIn("think", methods)
        self.assertIn("execute", methods)
        self.assertLessEqual(
            methods["think"].end_lineno
            - methods["think"].lineno,
            10,
        )
        self.assertLessEqual(
            methods["execute"].end_lineno
            - methods["execute"].lineno,
            10,
        )

    def test_router_owns_all_handler_dispatches(self) -> None:
        source = (
            self.project_root
            / "app/ai/brain_command_router.py"
        ).read_text(
            encoding="utf-8",
        )

        self.assertGreaterEqual(
            source.count("handler =="),
            10,
        )
        self.assertGreaterEqual(
            source.count("can_handle"),
            10,
        )

    def test_think_routing_preserves_autodev_behavior(self) -> None:
        brain = Brain.__new__(Brain)
        brain.cognitive = MagicMock()
        brain.software_engineer_controller = MagicMock()
        brain.software_engineer_controller.can_handle.return_value = False
        brain.autonomous_dev_controller = MagicMock()
        brain.autonomous_dev_controller.can_handle.return_value = False
        brain.architect_controller = MagicMock()
        brain.architect_controller.can_handle.return_value = False
        brain.meta_controller = MagicMock()
        brain.meta_controller.can_handle.return_value = False
        brain.executive_controller = MagicMock()
        brain.executive_controller.can_handle.return_value = False
        brain.director_controller = MagicMock()
        brain.director_controller.can_handle.return_value = False
        brain.improvement_controller = MagicMock()
        brain.improvement_controller.can_handle.return_value = False
        brain.evolution_controller = MagicMock()
        brain.evolution_controller.can_handle.return_value = False
        brain.continuous_dev_controller = MagicMock()
        brain.continuous_dev_controller.can_handle.return_value = False
        brain.reasoning_service = MagicMock()
        brain.reasoning_service.can_handle.return_value = False
        brain.research_service = MagicMock()
        brain.research_service.can_handle.return_value = False
        brain.autodev_router = MagicMock()
        brain.autodev_router.can_handle.return_value = True

        result = brain.think(
            "autodev status"
        )

        self.assertEqual(
            result["handler"],
            "autodev",
        )
        brain.cognitive.after_plan.assert_called_once()

    def test_execute_routing_preserves_controller_call(self) -> None:
        brain = Brain.__new__(Brain)
        brain._project_root = "C:/JarvisAI"
        brain.executive_controller = MagicMock()
        brain.executive_controller.handle.return_value = {
            "success": True,
            "status": "completed",
        }
        brain._format_executive_response = MagicMock(
            return_value="OK",
        )
        brain._remember_execution = MagicMock()

        result = brain.execute(
            {
                "command": "executive ai test",
                "handler": "executive_ai",
            }
        )

        self.assertEqual(result, "OK")
        brain.executive_controller.handle.assert_called_once()
        brain._remember_execution.assert_called_once_with(
            "executive ai test",
            "OK",
        )

    def test_router_is_stateless(self) -> None:
        self.assertEqual(
            vars(
                BrainCommandRouter()
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()

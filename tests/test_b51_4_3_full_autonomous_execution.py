from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.ai.planner_llm import PlannerLLM
from app.ai.software_engineer import (
    AutonomousSoftwareEngineerController,
)


class FakeQueue:

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_unique_task(self, **kwargs):
        self.calls.append(kwargs)
        return (
            SimpleNamespace(
                task_id=f"queue-{len(self.calls)}"
            ),
            True,
        )


class FakeImplementationExecutor:

    def __init__(
        self,
        result: dict | None = None,
    ) -> None:
        self.result = (
            result
            or {
                "success": True,
                "status": "COMPLETED",
                "workflow": {
                    "success": True,
                    "status": "completed",
                    "data": {
                        "rollback_attempted": False,
                        "rollback_success": False,
                    },
                },
            }
        )
        self.calls: list[dict[str, object]] = []

    def execute(
        self,
        task,
        *,
        auto_approve: bool,
        auto_rollback: bool,
    ):
        self.calls.append(
            {
                "task": task,
                "auto_approve": auto_approve,
                "auto_rollback": auto_rollback,
            }
        )
        return dict(self.result)


class SoftwareEngineerControllerTests(unittest.TestCase):

    def test_controller_detects_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Autonomous Software Engineer"
            )
        )

    def test_plan_without_target_is_queued(self) -> None:
        queue = FakeQueue()
        controller = AutonomousSoftwareEngineerController(
            project_root=".",
            task_queue=queue,
            implementation_executor=(
                FakeImplementationExecutor()
            ),
        )

        result = controller.handle(
            "Autonomous Software Engineer: dodaj raporty",
            {
                "auto_execute": True,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PLAN_READY",
        )
        self.assertGreater(
            result["queue"]["created"],
            0,
        )
        self.assertEqual(
            len(
                result["execution"]
            ),
            0,
        )

    def test_target_path_is_extracted_from_command(self) -> None:
        controller = AutonomousSoftwareEngineerController(
            project_root=".",
            implementation_executor=(
                FakeImplementationExecutor()
            ),
        )

        result = controller.handle(
            (
                "Zaimplementuj autonomicznie "
                "app/demo_feature.py nową klasę Demo"
            ),
            {
                "auto_execute": False,
            },
        )

        self.assertEqual(
            result["status"],
            "EXECUTION_READY",
        )
        self.assertEqual(
            result["target_path"],
            "app/demo_feature.py",
        )

    def test_full_execution_reaches_completed_status(self) -> None:
        executor = FakeImplementationExecutor()
        controller = AutonomousSoftwareEngineerController(
            project_root=".",
            implementation_executor=executor,
        )

        result = controller.handle(
            (
                "Zaimplementuj autonomicznie "
                "app/demo_feature.py nową klasę Demo"
            ),
            {
                "auto_execute": True,
                "auto_approve": True,
                "auto_rollback": True,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "COMPLETED",
        )
        self.assertEqual(len(executor.calls), 1)
        self.assertTrue(
            executor.calls[0]["auto_approve"]
        )

    def test_preview_status_is_preserved(self) -> None:
        executor = FakeImplementationExecutor(
            {
                "success": True,
                "status": "PREVIEW_READY",
                "workflow": {
                    "success": True,
                    "status": "waiting_for_approval",
                },
            }
        )
        controller = AutonomousSoftwareEngineerController(
            project_root=".",
            implementation_executor=executor,
        )

        result = controller.handle(
            (
                "Zaimplementuj autonomicznie "
                "app/demo_feature.py nową klasę Demo"
            ),
            {
                "auto_execute": True,
                "auto_approve": False,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PREVIEW_READY",
        )

    def test_planner_detects_software_engineer(self) -> None:
        planner = PlannerLLM()

        self.assertEqual(
            planner.detect_handler(
                "Zaimplementuj autonomicznie nową funkcję"
            ),
            "software_engineer",
        )

    def test_planner_creates_software_engineer_plan(self) -> None:
        planner = PlannerLLM()

        plan = planner.create_plan(
            "Autonomous Software Engineer"
        )

        self.assertTrue(plan["execute"])
        self.assertEqual(
            plan["handler_hint"],
            "software_engineer",
        )


class BrainSoftwareEngineerIntegrationTests(unittest.TestCase):

    def setUp(self) -> None:
        from app.ai.brain import Brain

        self.brain = Brain.__new__(
            Brain
        )
        self.brain.cognitive = MagicMock()
        self.brain.software_engineer_controller = (
            MagicMock()
        )
        self.brain.software_engineer_controller.can_handle.return_value = (
            True
        )
        self.brain.autonomous_dev_controller = (
            MagicMock()
        )
        self.brain.autonomous_dev_controller.can_handle.return_value = (
            False
        )
        self.brain._remember_execution = MagicMock()

    def test_brain_routes_to_software_engineer(self) -> None:
        thought = self.brain.think(
            "Autonomous Software Engineer"
        )

        self.assertEqual(
            thought["handler"],
            "autonomous_software_engineer",
        )
        self.brain.cognitive.after_plan.assert_called_once()

    def test_brain_executes_software_engineer(self) -> None:
        self.brain.software_engineer_controller.handle.return_value = {
            "success": True,
            "status": "COMPLETED",
            "plan": {
                "tasks": [
                    {},
                    {},
                ],
            },
            "queue": {
                "created": 0,
            },
            "target_path": "app/demo.py",
            "execution": {
                "attempt_count": 1,
            },
        }

        result = self.brain.execute(
            {
                "command": (
                    "Zaimplementuj autonomicznie "
                    "app/demo.py"
                ),
                "handler": (
                    "autonomous_software_engineer"
                ),
            }
        )

        self.assertIn(
            "Autonomous Software Engineer: COMPLETED",
            result,
        )
        self.assertIn(
            "Próby wykonania: 1",
            result,
        )


if __name__ == "__main__":
    unittest.main()

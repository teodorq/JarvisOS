import unittest
from unittest.mock import MagicMock

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
    AutonomousDevControllerPolicy,
)


class TestAutonomousGenerationCycle(
    unittest.TestCase
):

    def setUp(self) -> None:
        self.pipeline = MagicMock()
        self.pipeline.list_tasks.return_value = []
        self.pipeline.status.return_value = {
            "state": "stopped"
        }

        self.planner = MagicMock()
        self.planner.status.return_value = {}
        self.planner.complete_task.return_value = {
            "success": True
        }

        self.agent = MagicMock()
        self.developer = MagicMock()

        self.controller = AutonomousDevController(
            policy=AutonomousDevControllerPolicy(
                auto_start_pipeline=False
            ),
            pipeline=self.pipeline,
            planner=self.planner,
            developer_agent=self.agent,
            developer_controller=self.developer,
        )

        self.controller.last_planning_cycle = {
            "success": True,
            "status": "READY_FOR_CODE_GENERATION",
            "task": {
                "task_id": "plan-1",
                "title": "Refactor",
                "description": "Uprość moduł.",
                "target": "app/example.py",
                "priority_score": 90,
                "severity": "HIGH",
            },
            "plan": {
                "goal": "Uprość moduł."
            },
        }

    def test_missing_code_returns_required_status(
        self,
    ) -> None:

        result = self.controller.run_generation_cycle(
            context={
                "mode": "file",
                "path": "app/example.py",
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "CODE_INPUT_REQUIRED",
        )
        self.assertIn(
            "proposed_content",
            result["required"],
        )

    def test_valid_code_is_sent_to_developer(
        self,
    ) -> None:

        prepared = MagicMock()
        prepared.success = True
        prepared.status = "waiting_for_approval"
        prepared.message = "Patch gotowy."
        prepared.preview = "DIFF"
        prepared.errors = []

        self.developer.prepare.return_value = prepared

        result = self.controller.run_generation_cycle(
            context={
                "mode": "file",
                "path": "app/example.py",
                "proposed_content": "value = 1\n",
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "waiting_for_approval",
        )
        self.developer.reset.assert_called_once()
        self.developer.prepare.assert_called_once()

    def test_approve_can_execute_and_complete_task(
        self,
    ) -> None:

        approval = MagicMock()
        approval.success = True
        approval.as_dict.return_value = {
            "success": True,
            "status": "approved",
        }

        execution = MagicMock()
        execution.success = True
        execution.as_dict.return_value = {
            "success": True,
            "status": "completed",
        }

        self.developer.approve.return_value = approval
        self.developer.execute.return_value = execution

        self.controller.last_generation_cycle = {
            "planner_task_id": "plan-1"
        }

        result = (
            self.controller.approve_generated_change(
                auto_execute=True
            )
        )

        self.assertTrue(result["success"])
        self.planner.complete_task.assert_called_once_with(
            "plan-1"
        )


if __name__ == "__main__":
    unittest.main()

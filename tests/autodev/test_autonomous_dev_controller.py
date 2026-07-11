import unittest
from unittest.mock import MagicMock

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
    AutonomousDevControllerPolicy,
)


class TestAutonomousDevControllerPlanner(
    unittest.TestCase
):

    def setUp(self) -> None:
        self.pipeline = MagicMock()
        self.pipeline.status.return_value = {
            "state": "stopped"
        }
        self.pipeline.list_tasks.return_value = []

        self.planner = MagicMock()
        self.planner.status.return_value = {
            "backlog": {
                "total": 0
            }
        }
        self.planner.scan_and_plan.return_value = {
            "success": True,
            "files_scanned": 10,
            "scan_errors": [],
            "analyses_count": 10,
            "problems_count": 2,
            "backlog_count": 2,
            "next_task": {
                "task_id": "planned-1"
            },
            "tasks": [],
        }

        self.controller = AutonomousDevController(
            policy=AutonomousDevControllerPolicy(
                auto_start_pipeline=False
            ),
            pipeline=self.pipeline,
            planner=self.planner,
        )

    def test_scan_command_uses_planner(self) -> None:
        result = self.controller.handle(
            "autonomous dev scan"
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PROJECT_SCANNED",
        )
        self.assertEqual(
            result["problems_count"],
            2,
        )

    def test_status_contains_planner(self) -> None:
        result = self.controller.handle(
            "autonomous dev status"
        )

        self.assertTrue(result["success"])
        self.assertIn(
            "planner",
            result,
        )

    def test_next_task_falls_back_to_planner(
        self,
    ) -> None:
        self.planner.next_task.return_value = {
            "success": True,
            "status": "READY",
            "task": {
                "task_id": "planned-1"
            },
        }

        result = self.controller.next_task()

        self.assertEqual(
            result["status"],
            "PLANNED_TASK",
        )
        self.assertEqual(
            result["task"]["task_id"],
            "planned-1",
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
    AutonomousDevControllerPolicy,
)


class TestAutonomousPlanningCycle(
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
        self.planner.scan_and_plan.return_value = {
            "success": True,
            "files_scanned": 5,
            "scan_errors": [],
            "analyses_count": 5,
            "problems_count": 1,
            "backlog_count": 1,
            "next_task": {
                "task_id": "plan-1"
            },
            "tasks": [],
        }
        self.planner.claim_next_task.return_value = {
            "success": True,
            "status": "RUNNING",
            "task": {
                "task_id": "plan-1",
                "title": "Duży plik",
                "description": "Podziel moduł.",
                "recommendation": "Wydziel logikę.",
                "target": "app/example.py",
                "priority_score": 90.0,
                "severity": "HIGH",
            },
        }

        self.agent = MagicMock()
        self.agent.prepare_planned_task.return_value = {
            "success": True,
            "status": "PLAN_PREPARED",
            "task_id": "plan-1",
        }

        self.controller = AutonomousDevController(
            policy=AutonomousDevControllerPolicy(
                auto_start_pipeline=False
            ),
            pipeline=self.pipeline,
            planner=self.planner,
            developer_agent=self.agent,
        )

    def test_planning_cycle_prepares_next_task(
        self,
    ) -> None:

        result = self.controller.run_planning_cycle()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "READY_FOR_CODE_GENERATION",
        )
        self.assertEqual(
            result["task"]["task_id"],
            "plan-1",
        )
        self.agent.prepare_planned_task.assert_called_once()

    def test_planning_cycle_handles_empty_backlog(
        self,
    ) -> None:

        self.planner.claim_next_task.return_value = {
            "success": True,
            "status": "NO_TASKS",
            "task": None,
        }

        result = self.controller.run_planning_cycle()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "NO_TASKS",
        )

    def test_planning_failure_marks_task_failed(
        self,
    ) -> None:

        self.agent.prepare_planned_task.side_effect = (
            RuntimeError("plan error")
        )

        result = self.controller.run_planning_cycle()

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "PLANNING_FAILED",
        )
        self.planner.fail_task.assert_called_once_with(
            "plan-1",
            "plan error",
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
    AutonomousDevControllerPolicy,
)
from app.autodev.reasoning_memory import ReasoningMemory
from app.autodev.workflow_result import WorkflowResult


class TestSelfLearning(unittest.TestCase):

    def test_memory_accepts_generic_records(self) -> None:
        memory = ReasoningMemory()

        memory.remember(
            {
                "success": True,
                "goal": "test",
                "lessons": ["lesson-1"],
            }
        )

        memory.remember(
            {
                "success": False,
                "goal": "test-2",
                "lessons": ["lesson-2"],
            }
        )

        summary = memory.summary_dict()

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertIn("lesson-1", summary["lessons"])

    def test_workflow_result_stores_lessons(self) -> None:
        result = WorkflowResult(
            success=True,
            status="completed",
            message="ok",
        )

        result.add_lesson("validated")
        data = result.as_dict()

        self.assertEqual(
            data["learning_data"]["lessons"],
            ["validated"],
        )

    def test_controller_remembers_execution(self) -> None:
        pipeline = MagicMock()
        pipeline.list_tasks.return_value = []
        pipeline.status.return_value = {}

        planner = MagicMock()
        planner.status.return_value = {}
        planner.complete_task.return_value = {
            "success": True
        }

        developer = MagicMock()

        approval = MagicMock()
        approval.success = True
        approval.as_dict.return_value = {
            "success": True,
            "status": "approved",
        }

        execution = MagicMock()
        execution.success = True
        execution.status = "completed"
        execution.message = "done"
        execution.errors = []
        execution.as_dict.return_value = {
            "success": True,
            "status": "completed",
        }

        developer.approve.return_value = approval
        developer.execute.return_value = execution

        controller = AutonomousDevController(
            policy=AutonomousDevControllerPolicy(
                auto_start_pipeline=False
            ),
            pipeline=pipeline,
            planner=planner,
            developer_controller=developer,
        )

        controller.last_generation_cycle = {
            "planner_task_id": "task-1",
            "task": {
                "task_id": "task-1",
                "title": "Refactor",
                "description": "Improve module",
                "target": "app/example.py",
            },
        }

        result = controller.approve_generated_change(
            auto_execute=True
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            controller.learning_summary()["total"],
            1,
        )
        self.assertEqual(
            controller.learning_summary()["successful"],
            1,
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_feedback_loop import (
    AutonomousFeedbackLoop,
)


class TestAutonomousFeedbackLoop(unittest.TestCase):

    def test_executes_learns_and_queues_followup(self) -> None:
        lifecycle = MagicMock()
        lifecycle.run_next.return_value = {
            "success": True,
            "status": "COMPLETED",
            "selected_task": {
                "title": "Test task",
            },
        }

        controller = MagicMock()
        controller.queue_goal.return_value = {
            "success": True,
            "status": "QUEUED",
            "task_id": "next-1",
        }

        learning = MagicMock()
        learning.record.return_value = {
            "success": True,
        }
        learning.summary.return_value = {}

        generator = MagicMock()
        generator.generate.return_value = [
            {
                "goal": "Zweryfikuj zmianę",
                "priority": "NORMAL",
            }
        ]

        loop = AutonomousFeedbackLoop(
            lifecycle=lifecycle,
            controller=controller,
            learning=learning,
            generator=generator,
        )

        result = loop.run_cycle()

        self.assertTrue(
            result["success"]
        )
        controller.queue_goal.assert_called_once()
        learning.record.assert_called_once()

    def test_stops_when_no_tasks(self) -> None:
        lifecycle = MagicMock()
        lifecycle.run_next.return_value = {
            "success": True,
            "status": "NO_TASKS",
        }

        learning = MagicMock()
        learning.record.return_value = {
            "success": True,
        }
        learning.summary.return_value = {}

        generator = MagicMock()
        generator.generate.return_value = []

        loop = AutonomousFeedbackLoop(
            lifecycle=lifecycle,
            controller=MagicMock(),
            learning=learning,
            generator=generator,
        )

        result = loop.run(
            max_cycles=3
        )

        self.assertEqual(
            result["stop_reason"],
            "NO_TASKS",
        )
        self.assertEqual(
            result["cycles_run"],
            1,
        )


if __name__ == "__main__":
    unittest.main()

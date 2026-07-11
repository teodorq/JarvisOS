import unittest
from unittest.mock import MagicMock

from app.autodev.task_recovery import TaskRecovery


class TestTaskRecovery(unittest.TestCase):

    def test_recovers_interrupted_task(self) -> None:
        controller = MagicMock()
        controller.list_tasks.return_value = [
            {
                "task_id": "task-1",
                "status": "RUNNING",
            }
        ]

        result = TaskRecovery().recover(
            controller
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["recovered"],
            ["task-1"],
        )
        controller.retry_task.assert_called_once_with(
            "task-1",
            reset_attempts=False,
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock

from app.autodev.continuous_improvement_coordinator import (
    ContinuousImprovementCoordinator,
)


class TestContinuousImprovementCoordinator(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.pipeline = MagicMock()

        self.coordinator = (
            ContinuousImprovementCoordinator(
                pipeline=self.pipeline
            )
        )

    def test_processes_new_completed_task_once(
        self,
    ) -> None:

        self.pipeline.list_tasks.return_value = [
            {
                "task_id": "task-1",
                "status": "COMPLETED",
                "title": "Test task",
            }
        ]

        self.coordinator.improvement_loop.next_cycle = (
            MagicMock(
                return_value={
                    "success": True,
                    "cycle": 1,
                    "tasks_generated": 2,
                }
            )
        )

        first_result = (
            self.coordinator.process_completed_tasks()
        )

        second_result = (
            self.coordinator.process_completed_tasks()
        )

        self.assertEqual(
            first_result["completed_tasks_found"],
            1
        )

        self.assertEqual(
            first_result["cycles_started"],
            1
        )

        self.assertEqual(
            second_result["completed_tasks_found"],
            0
        )

        self.assertEqual(
            second_result["cycles_started"],
            0
        )

        self.coordinator.improvement_loop.next_cycle.assert_called_once()

    def test_ignores_non_completed_tasks(
        self,
    ) -> None:

        self.pipeline.list_tasks.return_value = [
            {
                "task_id": "task-2",
                "status": "RUNNING",
            }
        ]

        result = (
            self.coordinator.process_completed_tasks()
        )

        self.assertEqual(
            result["completed_tasks_found"],
            0
        )

        self.assertEqual(
            result["cycles_started"],
            0
        )

    def test_reset(
        self,
    ) -> None:

        self.coordinator.processed_task_ids.add(
            "task-1"
        )

        self.coordinator.reset()

        self.assertEqual(
            len(
                self.coordinator.processed_task_ids
            ),
            0
        )

        self.assertIsNone(
            self.coordinator.last_result
        )


if __name__ == "__main__":
    unittest.main()
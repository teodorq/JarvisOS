import unittest

from app.autodev.work_selector import WorkSelector


class TestWorkSelector(unittest.TestCase):

    def test_selects_highest_priority(self) -> None:
        selector = WorkSelector()

        selected = selector.select(
            [
                {
                    "task_id": "normal",
                    "priority": "NORMAL",
                    "status": "PENDING",
                },
                {
                    "task_id": "critical",
                    "priority": "CRITICAL",
                    "status": "PENDING",
                },
            ]
        )

        self.assertEqual(
            selected["task_id"],
            "critical",
        )

    def test_ignores_completed_tasks(self) -> None:
        selector = WorkSelector()

        selected = selector.select(
            [
                {
                    "task_id": "done",
                    "priority": "CRITICAL",
                    "status": "COMPLETED",
                }
            ]
        )

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()

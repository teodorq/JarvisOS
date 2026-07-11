import unittest

from app.autodev.followup_task_generator import (
    FollowupTaskGenerator,
)


class TestFollowupTaskGenerator(unittest.TestCase):

    def test_generates_recovery_tasks_after_failure(self) -> None:
        generator = FollowupTaskGenerator()

        tasks = generator.generate(
            {
                "status": "FAILED",
                "selected_task": {
                    "title": "Napraw moduł",
                    "target": "app/example.py",
                },
            }
        )

        self.assertEqual(
            len(tasks),
            2,
        )
        self.assertEqual(
            tasks[0]["priority"],
            "HIGH",
        )

    def test_generates_verification_after_success(self) -> None:
        generator = FollowupTaskGenerator()

        tasks = generator.generate(
            {
                "status": "COMPLETED",
                "selected_task": {
                    "title": "Dodaj funkcję",
                },
            }
        )

        self.assertEqual(
            len(tasks),
            1,
        )
        self.assertEqual(
            tasks[0]["priority"],
            "NORMAL",
        )


if __name__ == "__main__":
    unittest.main()

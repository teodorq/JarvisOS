import unittest
from unittest.mock import MagicMock

from app.autodev.project_health_cycle import (
    ProjectHealthCycle,
)


class TestProjectHealthCycle(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.pipeline = MagicMock()
        self.pipeline.start.return_value = True
        self.pipeline.is_running.return_value = False

        self.cycle = ProjectHealthCycle(
            pipeline=self.pipeline
        )

    def test_run_creates_tasks(
        self,
    ) -> None:

        self.cycle.monitor.analyze = MagicMock(
            return_value={
                "healthy": True,
                "issues": [],
                "suggestions": [
                    "Review Brain",
                ],
            }
        )

        self.cycle.seeder.seed = MagicMock(
            return_value={
                "success": True,
                "created_count": 1,
                "created_tasks": [
                    {
                        "title": "Review Brain",
                    }
                ],
                "errors": [],
            }
        )

        result = self.cycle.run()

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["tasks_created"],
            1
        )

        self.assertTrue(
            result["pipeline_started"]
        )

        self.pipeline.start.assert_called_once()

    def test_run_without_tasks(
        self,
    ) -> None:

        self.cycle.monitor.analyze = MagicMock(
            return_value={
                "healthy": True,
                "issues": [],
                "suggestions": [],
            }
        )

        self.cycle.seeder.seed = MagicMock(
            return_value={
                "success": True,
                "created_count": 0,
                "created_tasks": [],
                "errors": [],
            }
        )

        result = self.cycle.run()

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["tasks_created"],
            0
        )

        self.assertFalse(
            result["pipeline_started"]
        )

        self.pipeline.start.assert_not_called()

    def test_status(
        self,
    ) -> None:

        result = self.cycle.status()

        self.assertTrue(
            result["ready"]
        )

        self.assertFalse(
            result["pipeline_running"]
        )


if __name__ == "__main__":
    unittest.main()
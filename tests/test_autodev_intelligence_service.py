import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_intelligence_service import (
    AutoDevIntelligenceService,
)


class TestAutoDevIntelligenceService(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.self_review = MagicMock()
        self.planner = MagicMock()
        self.memory = MagicMock()
        self.trend_analyzer = MagicMock()

        self.service = AutoDevIntelligenceService(
            project_root="C:/JarvisAI",
            self_review=self.self_review,
            planner=self.planner,
            memory=self.memory,
            trend_analyzer=self.trend_analyzer,
        )

    def test_run_review_cycle(
        self,
    ) -> None:

        self.self_review.run.return_value = {
            "success": True,
            "average_score": 80.0,
            "findings": [
                {
                    "path": "C:/JarvisAI/app/test.py",
                    "score": 70.0,
                }
            ],
        }

        self.trend_analyzer.analyze.return_value = {
            "success": True,
            "trend": "STABLE",
            "recommendations": [
                "Kontynuuj dry-run."
            ],
        }

        self.planner.scan_and_plan.return_value = {
            "success": True,
            "next_task": {
                "task_id": "task-1"
            },
        }

        result = self.service.run_review_cycle()

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "INTELLIGENCE_CYCLE_COMPLETED"
        )

        self.assertTrue(
            result["safe_mode"]
        )

        self.assertFalse(
            result["writes_code"]
        )

    def test_status(
        self,
    ) -> None:

        self.self_review.status.return_value = {
            "ready": True
        }

        self.planner.status.return_value = {
            "ready": True
        }

        self.trend_analyzer.status.return_value = {
            "ready": True
        }

        result = self.service.status()

        self.assertEqual(
            result["project_root"],
            "C:/JarvisAI"
        )


if __name__ == "__main__":
    unittest.main()

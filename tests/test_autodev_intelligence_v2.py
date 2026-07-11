import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_intelligence_v2 import (
    AutoDevIntelligenceV2,
)
from app.autodev.improvement_priority_engine import (
    ImprovementPriorityEngine,
)


class TestAutoDevIntelligenceV2(
    unittest.TestCase
):

    def test_run_cycle_selects_candidate(
        self,
    ) -> None:

        service = MagicMock()
        priority_engine = MagicMock()

        service.run_review_cycle.return_value = {
            "success": True,
            "planning": {
                "tasks": [
                    {
                        "task_id": "task-1",
                        "target": "C:/JarvisAI/app/test.py",
                    }
                ]
            },
        }

        priority_engine.prioritize.return_value = {
            "success": True,
            "status": "IMPROVEMENT_SELECTED",
            "selected": {
                "task": {
                    "task_id": "task-1"
                }
            },
            "candidates": [],
        }

        intelligence = AutoDevIntelligenceV2(
            intelligence_service=service,
            priority_engine=priority_engine,
        )

        result = intelligence.run_cycle()

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "INTELLIGENCE_V2_COMPLETED"
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertTrue(
            result["requires_approval"]
        )

    def test_priority_engine_no_candidates(
        self,
    ) -> None:

        predictor = MagicMock()

        engine = ImprovementPriorityEngine(
            predictor=predictor
        )

        result = engine.prioritize(
            []
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "NO_CANDIDATES"
        )


if __name__ == "__main__":
    unittest.main()

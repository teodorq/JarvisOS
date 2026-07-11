import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_v3 import (
    AutoDevAutonomyV3,
)
from app.autodev.autodev_candidate_ranker import (
    AutoDevCandidateRanker,
)
from app.autodev.autodev_confidence_engine import (
    AutoDevConfidenceEngine,
)


class TestAutoDevAutonomyV3(
    unittest.TestCase
):

    def test_ranker_selects_best_candidate(
        self,
    ) -> None:

        ranker = AutoDevCandidateRanker()

        result = ranker.rank(
            [
                {
                    "goal": "Low",
                    "priority_score": 2,
                    "value_score": 2,
                    "risk_score": 10,
                },
                {
                    "goal": "High",
                    "priority_score": 20,
                    "value_score": 20,
                    "risk_score": 5,
                },
            ]
        )

        self.assertEqual(
            result["selected"]["goal"],
            "High"
        )

    def test_confidence_engine(
        self,
    ) -> None:

        engine = AutoDevConfidenceEngine()

        result = engine.calculate(
            {
                "priority_score": 20,
                "value_score": 20,
                "risk_score": 5,
            }
        )

        self.assertEqual(
            result["confidence_level"],
            "HIGH"
        )

    def test_autonomy_v3_runs_safe_preview(
        self,
    ) -> None:

        autonomy_v2 = MagicMock()

        autonomy_v2.run.return_value = {
            "success": True,
            "status": "AUTONOMY_V2_COMPLETED",
            "writes_code": False,
        }

        autonomy = AutoDevAutonomyV3(
            autonomy_v2=autonomy_v2
        )

        result = autonomy.run(
            [
                {
                    "goal": "Ulepsz pamięć",
                    "priority_score": 20,
                    "value_score": 20,
                    "risk_score": 5,
                }
            ]
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "AUTONOMY_V3_COMPLETED"
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )


if __name__ == "__main__":
    unittest.main()

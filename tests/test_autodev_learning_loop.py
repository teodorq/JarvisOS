import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_v2 import (
    AutoDevAutonomyV2,
)
from app.autodev.autodev_learning_loop import (
    AutoDevLearningLoop,
)


class TestAutoDevLearningLoop(
    unittest.TestCase
):

    def test_learning_loop(
        self,
    ) -> None:
        loop = AutoDevLearningLoop()

        result = loop.learn(
            cycle_result={
                "success": True,
                "status": "DRY_RUN_OK",
            },
            current_policy={
                "max_risk_score": 65.0,
            },
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "LEARNING_COMPLETED"
        )

        self.assertFalse(
            result["writes_code"]
        )

    def test_autonomy_v2(
        self,
    ) -> None:
        coordinator = MagicMock()

        coordinator.run.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
            "writes_code": False,
        }

        autonomy = AutoDevAutonomyV2(
            autonomy_coordinator=coordinator
        )

        result = autonomy.run(
            [
                {
                    "goal": "Ulepsz pamięć"
                }
            ]
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "AUTONOMY_V2_COMPLETED"
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )

    def test_policy_stays_safe(
        self,
    ) -> None:
        loop = AutoDevLearningLoop()

        result = loop.learn(
            cycle_result={
                "success": False,
                "status": "FAILED",
            },
            current_policy={
                "max_risk_score": 65.0,
                "require_approval": False,
                "dry_run": False,
            },
        )

        policy = result[
            "policy"
        ][
            "policy"
        ]

        self.assertTrue(
            policy["require_approval"]
        )

        self.assertTrue(
            policy["dry_run"]
        )


if __name__ == "__main__":
    unittest.main()

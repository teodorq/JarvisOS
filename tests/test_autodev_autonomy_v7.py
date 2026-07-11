import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_v7 import (
    AutoDevAutonomyV7,
)
from app.autodev.autodev_decision_policy import (
    AutoDevDecisionPolicy,
)


class TestAutoDevAutonomyV7(
    unittest.TestCase
):

    def test_builds_safe_approval_gate(
        self,
    ) -> None:
        autonomy_v6 = MagicMock()
        autonomy_v6.run.return_value = {
            "success": True,
            "status": "AUTONOMY_V6_COMPLETED",
            "cycle": {
                "plan": {
                    "optimized": {
                        "selected": {
                            "goal": "Ulepsz pamięć",
                            "priority_score": 20,
                            "risk_score": 10,
                            "value_score": 20,
                        }
                    }
                }
            },
            "writes_code": False,
        }

        autonomy = AutoDevAutonomyV7(
            autonomy_v6=autonomy_v6
        )

        result = autonomy.run()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "AUTONOMY_V7_READY",
        )
        self.assertTrue(
            result["decision"]["allowed"]
        )
        self.assertTrue(
            result["requires_approval"]
        )
        self.assertFalse(result["approved"])
        self.assertFalse(result["writes_code"])

    def test_blocks_high_risk_goal(
        self,
    ) -> None:
        autonomy_v6 = MagicMock()
        autonomy_v6.run.return_value = {
            "success": True,
            "status": "AUTONOMY_V6_COMPLETED",
            "intelligence": {
                "next_tasks": [
                    {
                        "goal": "Ryzykowna zmiana",
                        "priority_score": 100,
                        "risk_score": 90,
                    }
                ]
            },
            "writes_code": False,
        }

        autonomy = AutoDevAutonomyV7(
            autonomy_v6=autonomy_v6,
            decision_policy=AutoDevDecisionPolicy(
                max_risk_score=65
            ),
        )

        result = autonomy.run()

        self.assertEqual(
            result["decision"]["status"],
            "RISK_BLOCKED",
        )
        self.assertFalse(
            result["decision"]["allowed"]
        )
        self.assertFalse(result["writes_code"])

    def test_no_candidate_is_safe_noop(
        self,
    ) -> None:
        autonomy_v6 = MagicMock()
        autonomy_v6.run.return_value = {
            "success": True,
            "status": "NO_PROJECT_TASKS",
            "intelligence": {
                "next_tasks": []
            },
            "writes_code": False,
        }

        autonomy = AutoDevAutonomyV7(
            autonomy_v6=autonomy_v6
        )

        result = autonomy.run()

        self.assertEqual(
            result["status"],
            "NO_EXECUTION_CANDIDATE",
        )
        self.assertFalse(
            result["requires_approval"]
        )
        self.assertFalse(result["writes_code"])


if __name__ == "__main__":
    unittest.main()

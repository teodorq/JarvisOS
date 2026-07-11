import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_v5 import (
    AutoDevAutonomyV5,
)
from app.autodev.autodev_master_planner_v2 import (
    AutoDevMasterPlannerV2,
)
from app.autodev.autodev_task_ranker_v2 import (
    AutoDevTaskRankerV2,
)


class TestAutoDevAutonomyV5(
    unittest.TestCase
):

    def test_ranker_selects_best(
        self,
    ) -> None:
        ranker = AutoDevTaskRankerV2()

        result = ranker.rank(
            [
                {
                    "goal": "Low",
                    "priority_score": 1,
                    "value_score": 1,
                    "risk_score": 20,
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

    def test_master_plan(
        self,
    ) -> None:
        planner = AutoDevMasterPlannerV2()

        result = planner.plan(
            goals=[
                {
                    "goal": "Ulepsz pamięć",
                    "priority_score": 10,
                    "value_score": 10,
                    "risk_score": 5,
                }
            ],
            history_records=[
                {
                    "success": True,
                    "status": "DRY_RUN_OK",
                }
            ],
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "MASTER_PLAN_READY"
        )

        self.assertFalse(
            result["writes_code"]
        )

    def test_autonomy_v5(
        self,
    ) -> None:
        autonomy_v4 = MagicMock()

        autonomy_v4.run.return_value = {
            "success": True,
            "status": "AUTONOMY_V4_COMPLETED",
            "writes_code": False,
        }

        autonomy = AutoDevAutonomyV5(
            autonomy_v4=autonomy_v4
        )

        result = autonomy.run(
            goals=[
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
            "AUTONOMY_V5_COMPLETED"
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )


if __name__ == "__main__":
    unittest.main()

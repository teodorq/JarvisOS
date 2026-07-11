import unittest

from app.autodev.autodev_autonomy_v4 import (
    AutoDevAutonomyV4,
)
from app.autodev.autodev_goal_tree import (
    AutoDevGoalTree,
)
from app.autodev.autodev_multi_stage_planner import (
    AutoDevMultiStagePlanner,
)


class TestAutoDevAutonomyV4(
    unittest.TestCase
):

    def test_goal_tree(
        self,
    ) -> None:
        tree = AutoDevGoalTree()

        result = tree.build(
            root_goal="Ulepsz pamięć",
            steps=[
                "Analiza",
                "Plan",
            ],
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            len(result["nodes"]),
            3,
        )

    def test_multi_stage_plan(
        self,
    ) -> None:
        planner = AutoDevMultiStagePlanner()

        result = planner.plan(
            "Ulepsz pamięć"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "MULTI_STAGE_PLAN_READY"
        )

        self.assertFalse(
            result["writes_code"]
        )

    def test_autonomy_v4(
        self,
    ) -> None:
        autonomy = AutoDevAutonomyV4()

        result = autonomy.run(
            "Ulepsz pamięć"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "AUTONOMY_V4_COMPLETED"
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )


if __name__ == "__main__":
    unittest.main()

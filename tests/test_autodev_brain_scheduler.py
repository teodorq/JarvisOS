import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_brain_scheduler import (
    AutoDevBrainScheduler,
)
from app.autodev.autodev_cycle_coordinator import (
    AutoDevCycleCoordinator,
)


class TestAutoDevBrainScheduler(
    unittest.TestCase
):

    def test_selects_highest_priority(
        self,
    ) -> None:

        bridge = MagicMock()
        coordinator = AutoDevCycleCoordinator(
            bridge=bridge
        )

        scheduler = AutoDevBrainScheduler(
            coordinator=coordinator
        )

        result = scheduler.schedule(
            [
                {
                    "goal": "Low",
                    "priority_score": 1,
                },
                {
                    "goal": "High",
                    "priority_score": 10,
                },
            ]
        )

        self.assertEqual(
            result["status"],
            "GOAL_QUEUED"
        )

        self.assertEqual(
            result["selected"]["goal"],
            "High"
        )

    def test_run_next(
        self,
    ) -> None:

        bridge = MagicMock()

        bridge.handle.side_effect = [
            {
                "success": True,
                "status": "QUEUED",
            },
            {
                "success": True,
                "status": "DRY_RUN_OK",
                "writes_code": False,
            },
        ]

        coordinator = AutoDevCycleCoordinator(
            bridge=bridge
        )

        scheduler = AutoDevBrainScheduler(
            coordinator=coordinator
        )

        scheduler.schedule(
            [
                {
                    "goal": "Ulepsz pamięć",
                    "priority_score": 10,
                }
            ]
        )

        result = scheduler.run_next()

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "DRY_RUN_OK"
        )

    def test_no_goals(
        self,
    ) -> None:

        bridge = MagicMock()

        coordinator = AutoDevCycleCoordinator(
            bridge=bridge
        )

        scheduler = AutoDevBrainScheduler(
            coordinator=coordinator
        )

        result = scheduler.run_next()

        self.assertEqual(
            result["status"],
            "NO_GOALS"
        )


if __name__ == "__main__":
    unittest.main()

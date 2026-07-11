import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_coordinator import (
    AutoDevAutonomyCoordinator,
)
from app.autodev.autodev_brain_integration import (
    AutoDevBrainIntegration,
)


class TestAutoDevAutonomyCoordinator(
    unittest.TestCase
):

    def test_runs_safe_preview_cycle(
        self,
    ) -> None:

        scheduler = MagicMock()

        scheduler.schedule.return_value = {
            "success": True,
            "status": "GOAL_QUEUED",
        }

        scheduler.run_next.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
            "writes_code": False,
        }

        coordinator = AutoDevAutonomyCoordinator(
            brain_scheduler=scheduler
        )

        result = coordinator.run(
            [
                {
                    "goal": "Ulepsz pamięć",
                    "priority_score": 10.0,
                    "risk_score": 10.0,
                }
            ]
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "DRY_RUN_OK"
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )

    def test_blocks_high_risk_goal(
        self,
    ) -> None:

        scheduler = MagicMock()

        coordinator = AutoDevAutonomyCoordinator(
            brain_scheduler=scheduler
        )

        result = coordinator.run(
            [
                {
                    "goal": "Ryzykowna zmiana",
                    "priority_score": 10.0,
                    "risk_score": 90.0,
                }
            ]
        )

        self.assertEqual(
            result["status"],
            "RISK_BLOCKED"
        )

        scheduler.schedule.assert_not_called()

    def test_brain_integration_status(
        self,
    ) -> None:

        bridge = MagicMock()

        integration = AutoDevBrainIntegration(
            bridge=bridge
        )

        result = integration.handle(
            "jarvis autodev autonomy status"
        )

        self.assertEqual(
            result["status"],
            "AUTODEV_AUTONOMY_STATUS"
        )


if __name__ == "__main__":
    unittest.main()

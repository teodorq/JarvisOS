import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_cycle_manager import (
    AutoDevCycleManager,
)
from app.autodev.autodev_goal_manager import (
    AutoDevGoalManager,
)


class TestAutoDevCycleManager(
    unittest.TestCase
):

    def test_goal_manager_rejects_empty_goal(
        self,
    ) -> None:
        manager = AutoDevGoalManager()

        result = manager.normalize("   ")

        self.assertFalse(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "EMPTY_GOAL"
        )

    def test_preview_cycle_is_safe(
        self,
    ) -> None:
        runtime = MagicMock()

        runtime.preview.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
            "writes_code": False,
        }

        manager = AutoDevCycleManager(
            runtime_service=runtime
        )

        result = manager.run_preview_cycle(
            "Ulepsz moduł testowy"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )

        self.assertEqual(
            result["status"],
            "DRY_RUN_OK"
        )

        runtime.preview.assert_called_once()

    def test_metrics_after_cycle(
        self,
    ) -> None:
        runtime = MagicMock()

        runtime.preview.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        manager = AutoDevCycleManager(
            runtime_service=runtime
        )

        manager.run_preview_cycle(
            "Test"
        )

        status = manager.status()

        self.assertEqual(
            status["metrics"]["total_cycles"],
            1
        )


if __name__ == "__main__":
    unittest.main()

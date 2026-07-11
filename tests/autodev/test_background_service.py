import unittest
from unittest.mock import MagicMock

from app.autodev.background_service import BackgroundAutonomyService


class TestBackgroundAutonomyService(unittest.TestCase):

    def test_tick_delegates_to_worker(self) -> None:
        worker = MagicMock()
        worker.tick.return_value = {
            "success": True,
            "status": "SKIPPED",
        }

        service = BackgroundAutonomyService(
            worker=worker
        )

        result = service.tick()

        self.assertTrue(result["success"])
        worker.tick.assert_called_once_with()

    def test_user_activity_delegates_to_worker(self) -> None:
        worker = MagicMock()
        worker.on_user_activity.return_value = {
            "success": True,
            "status": "NO_ACTION",
        }

        service = BackgroundAutonomyService(
            worker=worker
        )

        result = service.user_activity()

        self.assertEqual(
            result["status"],
            "NO_ACTION",
        )


if __name__ == "__main__":
    unittest.main()

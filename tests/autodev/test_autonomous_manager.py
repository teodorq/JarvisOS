import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_manager import AutonomousManager


class TestAutonomousManager(unittest.TestCase):

    def test_stop_requests_loop_stop(self) -> None:
        loop = MagicMock()
        loop.status.return_value = {}

        manager = AutonomousManager(loop=loop)
        result = manager.stop()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "STOP_REQUESTED",
        )
        loop.request_stop.assert_called_once_with()

    def test_status_contains_loop(self) -> None:
        loop = MagicMock()
        loop.status.return_value = {
            "running": False
        }

        manager = AutonomousManager(loop=loop)
        result = manager.status()

        self.assertIn("loop", result)
        self.assertFalse(
            result["loop"]["running"]
        )


if __name__ == "__main__":
    unittest.main()

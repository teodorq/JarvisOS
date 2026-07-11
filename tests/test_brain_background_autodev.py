import unittest
from unittest.mock import MagicMock

from app.ai.brain import Brain


class TestBrainBackgroundAutoDev(unittest.TestCase):

    def setUp(self) -> None:
        self.brain = Brain.__new__(Brain)
        self.brain.cognitive = MagicMock()
        self.brain.memory = MagicMock()
        self.brain.background_commands = MagicMock()

    def test_think_routes_background_command(self) -> None:
        self.brain.background_commands.can_handle.return_value = True

        thought = self.brain.think(
            "background autodev status"
        )

        self.assertEqual(
            thought["handler"],
            "background_autodev",
        )
        self.assertTrue(
            thought["can_execute"]
        )

    def test_execute_background_command(self) -> None:
        self.brain.background_commands.handle.return_value = {
            "success": True,
            "status": "STARTED",
        }

        result = self.brain.execute(
            {
                "command": "background autodev start",
                "handler": "background_autodev",
            }
        )

        self.assertIn(
            "Status: STARTED",
            result,
        )
        self.brain.background_commands.handle.assert_called_once()

    def test_background_status(self) -> None:
        self.brain.background_commands.service.status.return_value = {
            "success": True,
            "status": "RUNNING",
            "running": True,
        }

        result = self.brain.background_status()

        self.assertTrue(
            result["running"]
        )


if __name__ == "__main__":
    unittest.main()

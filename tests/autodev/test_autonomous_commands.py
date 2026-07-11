import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_commands import AutonomousCommands


class TestAutonomousCommands(unittest.TestCase):

    def test_start_command(self) -> None:
        api = MagicMock()
        api.start.return_value = {
            "success": True,
            "status": "STARTED",
        }

        commands = AutonomousCommands(api=api)
        result = commands.handle(
            "autonomous start cycles 3"
        )

        self.assertTrue(result["success"])
        api.start.assert_called_once_with(
            max_cycles=3,
            background=True,
            context=None,
        )

    def test_status_command(self) -> None:
        api = MagicMock()
        api.status.return_value = {
            "success": True,
            "status": "STOPPED",
        }

        commands = AutonomousCommands(api=api)
        result = commands.handle(
            "autonomous status"
        )

        self.assertTrue(result["success"])
        api.status.assert_called_once_with()

    def test_unknown_command(self) -> None:
        commands = AutonomousCommands(
            api=MagicMock()
        )

        result = commands.handle(
            "autonomous something"
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "UNKNOWN_COMMAND",
        )


if __name__ == "__main__":
    unittest.main()

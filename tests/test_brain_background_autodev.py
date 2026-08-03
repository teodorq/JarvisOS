import unittest
from unittest.mock import MagicMock

from app.ai.brain import Brain


class TestBrainBackgroundAutoDev(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.brain = Brain.__new__(
            Brain
        )

        self.brain.cognitive = MagicMock()
        self.brain.memory = MagicMock()
        self.brain.autonomous_dev_controller = MagicMock()

    def test_think_routes_background_command(
        self,
    ) -> None:

        controller = (
            self.brain.autonomous_dev_controller
        )
        controller.can_handle.return_value = True

        thought = self.brain.think(
            "background autodev status"
        )

        self.assertEqual(
            thought["handler"],
            "autonomous_autodev",
        )
        self.assertTrue(
            thought["can_execute"]
        )

        controller.can_handle.assert_called_once_with(
            "background autodev status"
        )

    def test_execute_background_command(
        self,
    ) -> None:

        controller = (
            self.brain.autonomous_dev_controller
        )

        controller.handle.return_value = {
            "success": True,
            "status": "STARTED",
        }

        result = self.brain.execute(
            {
                "command": (
                    "background autodev start"
                ),
                "handler": (
                    "autonomous_autodev"
                ),
            }
        )

        self.assertIn(
            "Status: STARTED",
            result,
        )

        controller.handle.assert_called_once()

        self.brain.memory.add_history.assert_called_once()
        self.brain.cognitive.after_execute.assert_called_once()

    def test_background_status(
        self,
    ) -> None:

        controller = (
            self.brain.autonomous_dev_controller
        )

        controller.status.return_value = {
            "success": True,
            "status": "RUNNING",
            "running": True,
        }

        result = self.brain.background_status()

        self.assertTrue(
            result["running"]
        )
        self.assertEqual(
            result["status"],
            "RUNNING",
        )

        controller.status.assert_called_once()


if __name__ == "__main__":
    unittest.main()

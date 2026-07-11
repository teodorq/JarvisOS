import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_background_controller import (
    AutoDevBackgroundController,
)


class TestAutoDevBackgroundController(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.service = MagicMock()

        self.controller = (
            AutoDevBackgroundController(
                service=self.service,
                interval_seconds=0.1,
            )
        )

    def tearDown(
        self,
    ) -> None:

        self.controller.shutdown()

    def test_can_handle_start(
        self,
    ) -> None:

        self.assertTrue(
            self.controller.can_handle(
                "uruchom pętlę autodev"
            )
        )

    def test_can_handle_status(
        self,
    ) -> None:

        self.assertTrue(
            self.controller.can_handle(
                "status pętli autodev"
            )
        )

    def test_start_and_stop(
        self,
    ) -> None:

        start_result = self.controller.handle(
            "uruchom pętlę autodev"
        )

        self.assertIn(
            start_result["status"],
            {
                "BACKGROUND_STARTED",
                "BACKGROUND_ALREADY_RUNNING",
            },
        )

        stop_result = self.controller.handle(
            "zatrzymaj pętlę autodev"
        )

        self.assertIn(
            stop_result["status"],
            {
                "BACKGROUND_STOPPED",
                "BACKGROUND_ALREADY_STOPPED",
            },
        )

    def test_manual_cycle(
        self,
    ) -> None:

        self.service.run_cycle.return_value = {
            "success": True,
            "tasks_created": 2,
            "errors": [],
        }

        result = self.controller.handle(
            "wykonaj cykl autodev"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "BACKGROUND_CYCLE_COMPLETED"
        )

        self.service.run_cycle.assert_called_once()

    def test_status(
        self,
    ) -> None:

        result = self.controller.handle(
            "status autodev background"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "BACKGROUND_STATUS"
        )


if __name__ == "__main__":
    unittest.main()
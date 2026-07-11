import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_controller import (
    AutoDevAutonomyController,
)


class TestAutoDevAutonomyController(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.pipeline = MagicMock()

        self.pipeline.is_running.return_value = False
        self.pipeline.start.return_value = True

        self.controller = (
            AutoDevAutonomyController(
                pipeline=self.pipeline
            )
        )

    def test_can_handle_run_command(
        self,
    ) -> None:

        result = self.controller.can_handle(
            "uruchom autonomię autodev"
        )

        self.assertTrue(
            result
        )

    def test_can_handle_status_command(
        self,
    ) -> None:

        result = self.controller.can_handle(
            "status autonomii autodev"
        )

        self.assertTrue(
            result
        )

    def test_rejects_unrelated_command(
        self,
    ) -> None:

        result = self.controller.can_handle(
            "otwórz youtube"
        )

        self.assertFalse(
            result
        )

    def test_status(
        self,
    ) -> None:

        result = self.controller.handle(
            "status autonomii autodev"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "AUTONOMY_STATUS"
        )

    def test_run_cycle(
        self,
    ) -> None:

        self.controller.service.run_cycle = (
            MagicMock(
                return_value={
                    "success": True,
                    "tasks_created": 5,
                    "errors": [],
                }
            )
        )

        result = self.controller.handle(
            "uruchom autonomię autodev"
        )

        self.assertEqual(
            result["status"],
            "AUTONOMY_CYCLE_COMPLETED"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["tasks_created"],
            5
        )


if __name__ == "__main__":
    unittest.main()
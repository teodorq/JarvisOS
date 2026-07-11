import unittest
from unittest.mock import MagicMock

from app.autodev.brain_autodev_controller import (
    BrainAutoDevController,
)


class TestBrainAutoDevController(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.service = MagicMock()
        self.decision_engine = MagicMock()

        self.controller = BrainAutoDevController(
            service=self.service,
            decision_engine=self.decision_engine,
        )

    def test_can_handle_preview(
        self,
    ) -> None:

        self.assertTrue(
            self.controller.can_handle(
                "brain autodev preview"
            )
        )

    def test_preview(
        self,
    ) -> None:

        self.service.preview.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        result = self.controller.handle(
            "brain autodev preview"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["controller_status"],
            "BRAIN_AUTODEV_PREVIEW"
        )

        self.service.preview.assert_called_once()

    def test_execute(
        self,
    ) -> None:

        self.service.execute_approved.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        result = self.controller.handle(
            "wykonaj brain autodev"
        )

        self.assertEqual(
            result["controller_status"],
            "BRAIN_AUTODEV_EXECUTION"
        )

        self.service.execute_approved.assert_called_once()

    def test_decision(
        self,
    ) -> None:

        self.decision_engine.decide.return_value = {
            "success": True,
            "status": "DECISION_READY",
            "action": "GENERATE_LOCAL",
        }

        result = self.controller.handle(
            "decyzja brain autodev",
            context={
                "issue_type": "EMPTY_BLOCK"
            },
        )

        self.assertEqual(
            result["controller_status"],
            "BRAIN_AUTODEV_DECISION"
        )

        self.decision_engine.decide.assert_called_once_with(
            issue_type="EMPTY_BLOCK",
            context={
                "issue_type": "EMPTY_BLOCK"
            },
        )


if __name__ == "__main__":
    unittest.main()

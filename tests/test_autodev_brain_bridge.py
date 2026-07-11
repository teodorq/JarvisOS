import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_brain_bridge import (
    AutoDevBrainBridge,
)
from app.autodev.autodev_runtime_facade import (
    AutoDevRuntimeFacade,
)


class TestAutoDevBrainBridge(
    unittest.TestCase
):

    def test_queue_command(
        self,
    ) -> None:
        controller = MagicMock()
        controller.scheduler = MagicMock()
        controller.queue_service = MagicMock()
        controller.monitor = MagicMock()
        controller.runtime_service = MagicMock()

        controller.scheduler.schedule.return_value = {
            "success": True,
            "status": "QUEUED",
        }

        bridge = AutoDevBrainBridge(
            controller=controller
        )

        result = bridge.handle(
            "jarvis autodev queue Ulepsz pamięć"
        )

        self.assertEqual(
            result["status"],
            "QUEUED"
        )

    def test_status_command(
        self,
    ) -> None:
        controller = MagicMock()
        controller.scheduler = MagicMock()
        controller.queue_service = MagicMock()
        controller.monitor = MagicMock()
        controller.runtime_service = MagicMock()

        controller.monitor.status.return_value = {
            "status": "RUNTIME_MONITOR_READY"
        }

        bridge = AutoDevBrainBridge(
            controller=controller
        )

        result = bridge.handle(
            "jarvis autodev status"
        )

        self.assertEqual(
            result["status"],
            "BRAIN_BRIDGE_STATUS"
        )

    def test_facade_preview(
        self,
    ) -> None:
        controller = MagicMock()
        controller.scheduler = MagicMock()
        controller.queue_service = MagicMock()
        controller.monitor = MagicMock()
        controller.runtime_service = MagicMock()

        controller.runtime_service.preview.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
            "writes_code": False,
        }

        facade = AutoDevRuntimeFacade(
            controller=controller
        )

        result = facade.preview()

        self.assertTrue(
            result["success"]
        )

        self.assertFalse(
            result["writes_code"]
        )


if __name__ == "__main__":
    unittest.main()

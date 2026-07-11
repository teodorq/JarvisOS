import unittest
from unittest.mock import MagicMock

from app.ai.autodev_runtime_controller import (
    AutoDevRuntimeController,
)
from app.autodev.autodev_runtime_commands import (
    AutoDevRuntimeCommands,
)
from app.autodev.autodev_runtime_service import (
    AutoDevRuntimeService,
)


class TestAutoDevRuntimeController(
    unittest.TestCase
):

    def test_service_analyze_is_safe(
        self,
    ) -> None:

        intelligence = MagicMock()
        pipeline = MagicMock()
        orchestrator = MagicMock()
        session_manager = MagicMock()

        orchestrator.analyze.return_value = {
            "success": True,
            "status": "ANALYSIS_COMPLETED",
        }

        service = AutoDevRuntimeService(
            intelligence=intelligence,
            improvement_pipeline=pipeline,
            orchestrator=orchestrator,
            session_manager=session_manager,
        )

        result = service.analyze()

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["runtime_mode"],
            "ANALYZE"
        )

        self.assertFalse(
            result["approved"]
        )

        self.assertFalse(
            result["writes_code"]
        )

    def test_controller_preview(
        self,
    ) -> None:

        service = MagicMock()
        commands = AutoDevRuntimeCommands(
            service=service
        )

        service.preview.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
            "writes_code": False,
        }

        controller = AutoDevRuntimeController(
            service=service,
            commands=commands,
        )

        result = controller.handle(
            "autodev runtime preview",
            context={
                "source": "Brain"
            },
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["controller"],
            "AutoDevRuntimeController"
        )

        self.assertEqual(
            result["context"]["source"],
            "Brain"
        )

        service.preview.assert_called_once()

    def test_controller_status(
        self,
    ) -> None:

        service = MagicMock()

        service.status.return_value = {
            "success": True,
            "status": "AUTODEV_RUNTIME_STATUS",
        }

        commands = AutoDevRuntimeCommands(
            service=service
        )

        controller = AutoDevRuntimeController(
            service=service,
            commands=commands,
        )

        result = controller.handle(
            "autodev runtime status"
        )

        self.assertEqual(
            result["status"],
            "AUTODEV_RUNTIME_STATUS"
        )

        service.status.assert_called_once()


if __name__ == "__main__":
    unittest.main()

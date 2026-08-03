from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_long_running_router import (
    SoftwareEngineerLongRunningRouter,
)
from app.gui.command_safety import (
    is_read_only_learning_command,
)


COMMAND = "Uruchom nadzorcę autonomii"


class B531SupervisorCommandRoutingFixTests(unittest.TestCase):

    def test_controller_accepts_exact_gui_start_command(
        self,
    ) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                COMMAND
            )
        )

    def test_router_accepts_accusative_polish_form(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            service = MagicMock()
            service.start_background.return_value = {
                "success": True,
                "status": "LONG_RUNNING_SUPERVISOR_STARTED",
                "operation": "long_running_autonomy",
                "errors": [],
            }
            controller = SimpleNamespace(
                project_root=Path(directory),
                long_running_autonomy_service=service,
                _normalize=(
                    AutonomousSoftwareEngineerController._normalize
                ),
            )

            result = SoftwareEngineerLongRunningRouter().try_handle(
                controller,
                command=COMMAND,
                objective=COMMAND,
                context={},
            )

        self.assertIsNotNone(result)
        self.assertEqual(
            result["status"],
            "LONG_RUNNING_SUPERVISOR_STARTED",
        )
        service.start_background.assert_called_once_with()

    def test_brain_routes_exact_command_to_software_engineer(
        self,
    ) -> None:
        cognitive = MagicMock()
        brain = SimpleNamespace(
            cognitive=cognitive,
            software_engineer_controller=SimpleNamespace(
                can_handle=(
                    AutonomousSoftwareEngineerController.can_handle
                ),
            ),
        )

        thought = BrainCommandRouter().think(
            brain,
            COMMAND,
        )

        self.assertEqual(
            thought["handler"],
            "autonomous_software_engineer",
        )
        self.assertTrue(thought["can_execute"])

    def test_start_command_still_requires_confirmation(
        self,
    ) -> None:
        self.assertFalse(
            is_read_only_learning_command(
                COMMAND
            )
        )

    def test_ascii_variant_is_supported(
        self,
    ) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Uruchom nadzorce autonomii"
            )
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)


class B571GuiRoutingFixTests(unittest.TestCase):
    """Regression coverage for the real GUI routing failure in B57."""

    def test_controller_gate_accepts_exact_gui_status_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Pokaż status rozwoju strategicznego"
            )
        )

    def test_controller_gate_accepts_all_primary_b57_commands(self) -> None:
        commands = (
            "Uruchom rozwój strategiczny",
            "Wstrzymaj rozwój strategiczny",
            "Wznów rozwój strategiczny",
            "Zatrzymaj rozwój strategiczny",
            "Pokaż roadmapę rozwoju",
            "Historia rozwoju strategicznego",
            "Status B57",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(
                    AutonomousSoftwareEngineerController.can_handle(command)
                )

    def test_full_controller_flow_reaches_b57_status_service(self) -> None:
        service = MagicMock()
        service.status.return_value = {
            "success": True,
            "status": "STRATEGIC_DEVELOPMENT_STATUS",
            "operation": "strategic_development",
        }
        controller = AutonomousSoftwareEngineerController.__new__(
            AutonomousSoftwareEngineerController
        )
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_development_router."
            "bootstrap_strategic_development",
            return_value=service,
        ):
            result = controller.handle(
                "Pokaż status rozwoju strategicznego",
                context={"auto_approve": False},
            )
        self.assertEqual(
            result["status"],
            "STRATEGIC_DEVELOPMENT_STATUS",
        )
        service.status.assert_called_once_with()

    def test_brain_selects_software_engineer_for_b57_status(self) -> None:
        software_engineer = MagicMock()
        software_engineer.can_handle.side_effect = (
            AutonomousSoftwareEngineerController.can_handle
        )
        brain = SimpleNamespace(
            cognitive=MagicMock(),
            software_engineer_controller=software_engineer,
        )
        thought = BrainCommandRouter().think(
            brain,
            "Pokaż status rozwoju strategicznego",
        )
        self.assertEqual(
            thought["handler"],
            "autonomous_software_engineer",
        )


if __name__ == "__main__":
    unittest.main()

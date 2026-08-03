from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import ast
import unittest

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_strategic_execution_router import (
    SoftwareEngineerStrategicExecutionRouter,
)


class B583GuiGateRoutingFixTests(unittest.TestCase):
    """B58 commands pass the main software-engineer GUI gate."""

    def test_controller_gate_accepts_primary_b58_commands(self) -> None:
        commands = (
            "Pokaż status wykonania strategicznego",
            "Uruchom wykonanie strategiczne",
            "Wykonaj następne zadanie strategiczne",
            "Synchronizuj wykonanie strategiczne",
            "Wstrzymaj wykonanie strategiczne",
            "Wznów wykonanie strategiczne",
            "Zatrzymaj wykonanie strategiczne",
            "Status B58",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(
                    SoftwareEngineerStrategicExecutionRouter.can_handle(command)
                )
                self.assertTrue(
                    AutonomousSoftwareEngineerController.can_handle(command)
                )

    def test_brain_selects_software_engineer_for_b58_dispatch(self) -> None:
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
            "Wykonaj następne zadanie strategiczne",
        )

        self.assertEqual(
            thought["handler"],
            "autonomous_software_engineer",
        )

    def test_full_controller_flow_reaches_b58_dispatch_service(self) -> None:
        service = MagicMock()
        service.dispatch_next.return_value = {
            "success": True,
            "status": "STRATEGIC_EXECUTION_JOB_DISPATCHED",
            "job_id": "longrun-b58-gate",
        }
        controller = AutonomousSoftwareEngineerController.__new__(
            AutonomousSoftwareEngineerController
        )

        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_execution_router."
            "bootstrap_strategic_execution",
            return_value=service,
        ):
            result = controller.handle(
                "Wykonaj następne zadanie strategiczne",
                context={
                    "operation": "strategic_execution_status",
                    "auto_approve": False,
                },
            )

        self.assertEqual(
            result["status"],
            "STRATEGIC_EXECUTION_JOB_DISPATCHED",
        )
        service.dispatch_next.assert_called_once_with()
        service.status.assert_not_called()

    def test_controller_remains_below_audit_limit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = (
            root
            / "app/ai/software_engineer/autonomous_software_engineer.py"
        )
        source = path.read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 440)
        ast.parse(source)


if __name__ == "__main__":
    unittest.main()

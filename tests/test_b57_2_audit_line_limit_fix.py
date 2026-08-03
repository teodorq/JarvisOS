from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_strategic_development_router import (
    SoftwareEngineerStrategicDevelopmentRouter,
)


class B572AuditLineLimitFixTests(unittest.TestCase):
    """B57 routing remains reachable without breaking controller audit limits."""

    def test_controller_stays_below_audit_limit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = (
            root
            / "app/ai/software_engineer/autonomous_software_engineer.py"
        )
        source = path.read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 440)
        ast.parse(source)

    def test_strategic_router_owns_b57_command_phrases(self) -> None:
        commands = (
            "Pokaż status rozwoju strategicznego",
            "Uruchom rozwój strategiczny",
            "Wstrzymaj rozwój strategiczny",
            "Wznów rozwój strategiczny",
            "Zatrzymaj rozwój strategiczny",
            "Pokaż roadmapę rozwoju",
            "Historia rozwoju strategicznego",
            "Status B57",
            "Strategic development status",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(
                    SoftwareEngineerStrategicDevelopmentRouter.can_handle(
                        command
                    )
                )

    def test_controller_gate_delegates_b57_recognition(self) -> None:
        commands = (
            "Pokaż status rozwoju strategicznego",
            "Uruchom rozwój strategiczny",
            "Pokaż roadmapę rozwoju",
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

    def test_brain_selects_software_engineer_for_b57(self) -> None:
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

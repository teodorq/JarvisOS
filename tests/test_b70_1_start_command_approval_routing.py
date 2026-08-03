from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_autonomy_governance_router import (
    SoftwareEngineerAutonomyGovernanceRouter,
)
from app.gui.command_safety import is_read_only_learning_command


class _FakeController:
    strategic_policy_validation_service = object()

    @staticmethod
    def _normalize(command: str) -> str:
        return " ".join(str(command).casefold().split())


class B701StartCommandApprovalRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = SoftwareEngineerAutonomyGovernanceRouter()

    def test_natural_recovery_aliases_are_recognized(self) -> None:
        commands = (
            "Uruchom odzyskiwanie autonomii",
            "Uruchom autonomiczne odzyskiwanie",
            "Zatrzymaj odzyskiwanie autonomii",
            "Wstrzymaj odzyskiwanie autonomii",
            "Wznów odzyskiwanie autonomii",
            "Wznow odzyskiwanie autonomii",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(self.router.can_handle(command))
                self.assertTrue(
                    AutonomousSoftwareEngineerController.can_handle(command)
                )

    def test_natural_aliases_map_to_b70_supervisor_actions(self) -> None:
        checks = {
            "uruchom odzyskiwanie autonomii": "b70_start",
            "uruchom autonomiczne odzyskiwanie": "b70_start",
            "zatrzymaj odzyskiwanie autonomii": "b70_stop",
            "wstrzymaj odzyskiwanie autonomii": "b70_pause",
            "wznów odzyskiwanie autonomii": "b70_resume",
            "wznow odzyskiwanie autonomii": "b70_resume",
        }
        for command, expected in checks.items():
            with self.subTest(command=command):
                self.assertEqual(
                    self.router._action("", command),
                    expected,
                )

    def test_start_alias_dispatches_to_recovery_supervisor(self) -> None:
        recovery = SimpleNamespace(
            start_background=MagicMock(return_value={
                "success": True,
                "status": "AUTONOMOUS_RECOVERY_SUPERVISOR_STARTED",
            })
        )
        fallback = MagicMock()
        suite = SimpleNamespace(
            safe_policy_deployment=fallback,
            goal_governance=fallback,
            resource_budget=fallback,
            causal_learning=fallback,
            release_manager=fallback,
            self_maintenance=fallback,
            full_autonomy=fallback,
            incident_response=fallback,
            recovery_orchestrator=recovery,
        )

        with patch(
            "app.ai.software_engineer."
            "software_engineer_autonomy_governance_router."
            "bootstrap_autonomy_governance_suite",
            return_value=suite,
        ):
            result = self.router.try_handle(
                _FakeController(),
                command="Uruchom odzyskiwanie autonomii",
                objective="Uruchom odzyskiwanie autonomii",
                context={},
            )

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_RECOVERY_SUPERVISOR_STARTED",
        )
        recovery.start_background.assert_called_once_with()

    def test_mutating_alias_requires_confirmation_context(self) -> None:
        self.assertFalse(is_read_only_learning_command(
            "Uruchom odzyskiwanie autonomii"
        ))
        self.assertFalse(is_read_only_learning_command(
            "Zatrzymaj odzyskiwanie autonomii"
        ))
        self.assertTrue(is_read_only_learning_command(
            "Pokaż status odzyskiwania autonomii"
        ))


if __name__ == "__main__":
    unittest.main()

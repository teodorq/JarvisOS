from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_strategic_policy_router import (
    SoftwareEngineerStrategicPolicyRouter,
)
from app.gui.command_safety import is_read_only_learning_command


class B601LearningCycleCommandAliasTests(unittest.TestCase):
    def test_polish_przeprowadz_alias_reaches_b60_gate(self) -> None:
        command = "Przeprowadź cykl samouczenia strategicznego"
        self.assertTrue(SoftwareEngineerStrategicPolicyRouter.can_handle(command))
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(command))

    def test_alias_is_mutating_and_requires_confirmation(self) -> None:
        self.assertFalse(
            is_read_only_learning_command(
                "Przeprowadź cykl samouczenia strategicznego"
            )
        )

    def test_alias_overrides_stale_status_context(self) -> None:
        router = SoftwareEngineerStrategicPolicyRouter()
        self.assertEqual(
            router._action(
                "strategic_policy_status",
                "przeprowadź cykl samouczenia strategicznego",
            ),
            "learn",
        )

    def test_alias_dispatches_learning_cycle(self) -> None:
        router = SoftwareEngineerStrategicPolicyRouter()
        service = MagicMock()
        service.learn.return_value = {
            "success": True,
            "status": "STRATEGIC_POLICY_EVOLUTION_HOLD",
        }
        controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split())
        )
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_policy_router."
            "bootstrap_strategic_policy_evolution",
            return_value=service,
        ):
            result = router.try_handle(
                controller,
                command="Przeprowadź cykl samouczenia strategicznego",
                objective="",
                context={"operation": "strategic_policy_status"},
            )
        self.assertEqual(
            result["status"],
            "STRATEGIC_POLICY_EVOLUTION_HOLD",
        )
        service.learn.assert_called_once_with(apply_if_safe=None)


if __name__ == "__main__":
    unittest.main()

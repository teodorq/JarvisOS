from __future__ import annotations

import unittest

from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_autonomy_governance_router import (
    SoftwareEngineerAutonomyGovernanceRouter,
)
from app.gui.command_safety import is_read_only_learning_command


class B691IncidentCenterCommandRoutingTests(unittest.TestCase):
    def test_center_aliases_are_recognized(self):
        router = SoftwareEngineerAutonomyGovernanceRouter()
        expectations = {
            "Uruchom centrum incydentów": "b69_start",
            "Zatrzymaj centrum incydentów": "b69_stop",
            "Wstrzymaj centrum incydentów": "b69_pause",
            "Wznów centrum incydentów": "b69_resume",
        }
        for command, action in expectations.items():
            normalized = " ".join(command.casefold().split())
            self.assertTrue(router.can_handle(command), command)
            self.assertEqual(router._action("", normalized), action)

    def test_main_controller_gate_accepts_start_center_command(self):
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(
            "Uruchom centrum incydentów"
        ))

    def test_center_start_is_mutating_not_read_only(self):
        self.assertFalse(is_read_only_learning_command(
            "Uruchom centrum incydentów"
        ))


if __name__ == "__main__":
    unittest.main()

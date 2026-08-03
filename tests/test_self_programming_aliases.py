from __future__ import annotations

import unittest

from app.ai.software_engineer.autonomous_cycle_commands import (
    plan_autonomous_cycle_command,
)
from app.gui.client_capability_policy import ClientCapabilityPolicy


class SelfProgrammingAliasTests(unittest.TestCase):
    def test_owner_phrases_prepare_one_isolated_programming_cycle(self) -> None:
        for command in (
            "Programuj siebie",
            "Sam się programuj",
            "Zacznij samoprogramowanie",
        ):
            thought = plan_autonomous_cycle_command(object(), command)
            self.assertIsNotNone(thought)
            self.assertEqual(thought["handler"], "autonomous_cycle_run")
            self.assertTrue(thought["workspace_only"])
            self.assertFalse(thought["project_write"])
            self.assertFalse(thought["auto_deploy"])

    def test_client_cannot_use_self_programming_phrases(self) -> None:
        for command in (
            "Programuj siebie",
            "Sam się programuj",
            "Zacznij samoprogramowanie",
        ):
            denial = ClientCapabilityPolicy.denial_message(command)
            self.assertIn("tylko w trybie właściciela", denial)


if __name__ == "__main__":
    unittest.main()

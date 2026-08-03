from __future__ import annotations

import unittest

from app.ai.software_engineer.autonomous_cycle_commands import (
    plan_autonomous_cycle_command,
)
from app.ai.unified_intent_router import DEFAULT_INTENT_ROUTER
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.gui.self_development_console import is_real_development_thought


class NaturalSelfDevelopmentIntentTests(unittest.TestCase):
    def test_owner_can_start_one_safe_cycle_naturally(self) -> None:
        thought = plan_autonomous_cycle_command(
            object(), "Zacznij samorozwój JARVISA"
        )
        self.assertIsNotNone(thought)
        self.assertEqual(thought["handler"], "autonomous_cycle_run")
        self.assertTrue(thought["workspace_only"])
        self.assertFalse(thought["project_write"])
        self.assertFalse(thought["auto_approve"])
        self.assertFalse(thought["auto_deploy"])
        self.assertTrue(is_real_development_thought(thought))

    def test_status_resume_and_cancel_are_natural_cycle_commands(self) -> None:
        expected = {
            "Status samorozwoju": "autodev_cycle_status",
            "Kontynuuj samorozwój": "autodev_cycle_resume",
            "Zatrzymaj samorozwój": "autodev_cycle_cancel",
        }
        for command, intent in expected.items():
            decision = DEFAULT_INTENT_ROUTER.route(command)
            self.assertIsNotNone(decision)
            self.assertEqual(decision.intent, intent)

    def test_client_cannot_start_owner_self_development(self) -> None:
        for command in (
            "Zacznij samorozwój",
            "Rozwijaj siebie",
            "Ulepsz siebie",
        ):
            denial = ClientCapabilityPolicy.denial_message(command)
            self.assertIn("tylko w trybie właściciela", denial)


if __name__ == "__main__":
    unittest.main()

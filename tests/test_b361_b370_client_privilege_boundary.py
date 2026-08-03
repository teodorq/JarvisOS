from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.gui.client_command_runtime import ClientCommandRuntimeMixin
from app.gui.client_execution_scope import (
    approve_client_thought,
    client_execution_denial,
    scope_client_thought,
)


class TestB361B370ClientPrivilegeBoundary(unittest.TestCase):
    def test_manifest_closes_every_stage_and_keeps_owner_return(self) -> None:
        manifest = json.loads(
            Path("config/b361_b370_client_privilege_boundary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            list(manifest["stages"]),
            [f"B{number}" for number in range(361, 371)],
        )
        self.assertEqual(manifest["access"]["client_to_owner"], "PIN_REQUIRED")
        self.assertFalse(manifest["access"]["client_can_confirm_owner_plan"])

    def test_structural_owner_handlers_and_actions_are_blocked(self) -> None:
        blocked = (
            {"handler": "reasoner"},
            {"handler": "research"},
            {"handler": "meta_executive"},
            {"handler": "safe_development_apply"},
            {"handler": "standard", "actions": [{"action_type": "run_command"}]},
        )
        for thought in blocked:
            with self.subTest(thought=thought):
                self.assertIn(
                    "tylko w trybie właściciela",
                    ClientCapabilityPolicy.denial_for_thought(thought),
                )
        self.assertEqual(
            ClientCapabilityPolicy.denial_for_thought({
                "handler": "standard",
                "actions": [{"action_type": "open_app"}],
            }),
            "",
        )

    def test_only_a_plan_scoped_by_this_client_session_can_execute(self) -> None:
        window = SimpleNamespace(_client_scope_enforced=True)
        safe = {"handler": "personal_assistant", "assistant_intent": "calendar_create"}
        self.assertIn("nie przygotowano", client_execution_denial(window, safe))
        scoped = scope_client_thought(window, safe)
        self.assertEqual(client_execution_denial(window, scoped), "")
        self.assertIn(
            "nie przygotowano",
            client_execution_denial(
                SimpleNamespace(_client_scope_enforced=True), scoped
            ),
        )

    def test_owner_pending_plan_cannot_be_confirmed_from_client(self) -> None:
        events: list[dict] = []
        spoken: list[str] = []
        window = SimpleNamespace(
            pending_thought={"handler": "reasoner", "can_execute": True},
            _publish_client_event=lambda **event: events.append(event),
            say_safe=spoken.append,
        )
        ClientCommandRuntimeMixin._handle_client_confirmation(window, "tak")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["state"], "error")
        self.assertIn("trybie właściciela", spoken[0])
        self.assertIsNotNone(window.pending_thought)

    def test_denial_is_published_before_direct_execution(self) -> None:
        events: list[dict] = []
        spoken: list[str] = []
        window = SimpleNamespace(
            _client_scope_enforced=True,
            _publish_client_event=lambda **event: events.append(event),
            say_safe=spoken.append,
        )
        self.assertFalse(approve_client_thought(window, {"handler": "standard"}))
        self.assertEqual(events[0]["progress"], 100)
        self.assertTrue(spoken)

    def test_both_sync_and_background_paths_recheck_scope(self) -> None:
        sync = Path("app/gui/client_command_runtime.py").read_text(encoding="utf-8")
        background = Path("app/gui/client_background_commands.py").read_text(
            encoding="utf-8"
        )
        owner_access = Path("app/gui/client_experience_window.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("approve_client_thought(self, thought)", sync)
        self.assertIn("client_execution_denial(self.window, thought)", background)
        self.assertIn('QKeySequence("Ctrl+Shift+F12")', owner_access)


if __name__ == "__main__":
    unittest.main()

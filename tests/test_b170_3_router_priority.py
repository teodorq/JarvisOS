from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from app.gui.active_resolution_priority import (
    active_resolution_priority_thought,
)


class _Memory:
    def __init__(self, suggestion=None):
        self.suggestion = dict(suggestion or {})

    def last_suggestion(self):
        return dict(self.suggestion)


class _Natural:
    def __init__(self, suggestion=None):
        self.runtime = SimpleNamespace(
            active=SimpleNamespace(memory=_Memory(suggestion))
        )
        self.commands = []

    def plan(self, command):
        self.commands.append(str(command))
        return {
            "handler": "personal_assistant",
            "natural_action": True,
            "assistant_intent": "active_apply_suggestion",
            "natural_slots": {"event_id": "event-b"},
            "requires_confirmation": True,
            "can_execute": True,
            "read_only": False,
        }


class B1703RouterPriorityTests(unittest.TestCase):
    def window(self, suggestion=None):
        natural = _Natural(suggestion)
        return (
            SimpleNamespace(
                assistant=SimpleNamespace(natural_actions=natural)
            ),
            natural,
        )

    def test_active_suggestion_wins_for_zrob_to(self):
        window, natural = self.window({"kind": "calendar_move"})
        thought = active_resolution_priority_thought(window, "Zrób to")
        self.assertEqual(thought["assistant_intent"], "active_apply_suggestion")
        self.assertEqual(thought["natural_slots"]["event_id"], "event-b")
        self.assertEqual(natural.commands, ["Zrób to"])

    def test_variants_keep_active_resolution_priority(self):
        for command in (
            "wykonaj to",
            "Zastosuj propozycję",
            "wykonaj propozycję",
            "tak zrób",
        ):
            with self.subTest(command=command):
                window, _natural = self.window({"kind": "calendar_move"})
                self.assertIsNotNone(
                    active_resolution_priority_thought(window, command)
                )

    def test_no_suggestion_does_not_steal_owner_command(self):
        window, natural = self.window()
        self.assertIsNone(
            active_resolution_priority_thought(window, "Zrób to")
        )
        self.assertEqual(natural.commands, [])

    def test_unrelated_command_does_not_use_priority_route(self):
        window, natural = self.window({"kind": "calendar_move"})
        self.assertIsNone(
            active_resolution_priority_thought(window, "Status Google Workspace")
        )
        self.assertEqual(natural.commands, [])

    def test_owner_runtime_checks_priority_before_brain(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "app/gui/business_command_runtime.py"
        ).read_text(encoding="utf-8")
        priority = source.index(
            "active_resolution_priority_thought(self, text)"
        )
        global_route = source.index("self.brain.think(text)")
        self.assertLess(priority, global_route)

    def test_source_limits_and_no_hardcoded_project_path(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/business_command_runtime.py": 180,
            "app/gui/active_resolution_priority.py": 80,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

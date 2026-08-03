from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.gui.confirmation_revision_runtime import handle_owner_confirmation
from app.natural_actions.revisions import rebuild_command
from app.natural_actions.validation import classify_confirmation


class _Console:
    def __init__(self) -> None:
        self.lines = []
        self.states = []
    def append(self, text: str) -> None:
        self.lines.append(text)
    def set_state(self, text: str, kind: str) -> None:
        self.states.append((text, kind))


class _Brain:
    def __init__(self) -> None:
        self.executed = []
    def execute(self, thought: dict) -> str:
        self.executed.append(dict(thought))
        return "Wykonano"


class _Window:
    def __init__(self) -> None:
        self.pending_thought = {
            "assistant_intent": "calendar_create",
            "natural_slots": {
                "title": "trening",
                "when": "2026-07-28T18:00:00+02:00",
                "duration_minutes": 60,
                "reminder_minutes": 20,
            },
        }
        self.console_page = _Console()
        self.brain = _Brain()
        self.spoken = []
        self.replanned = []
    def say_safe(self, text: str) -> None:
        self.spoken.append(text)
    def process_command(self, text: str, source: str = "Ty") -> None:
        self.replanned.append((text, source))


class B1504ConfirmationCompatibilityTests(unittest.TestCase):
    def test_compound_no_is_revision(self) -> None:
        self.assertEqual(classify_confirmation("Nie, jednak o 19").kind, "revise")

    def test_revision_changes_hour_and_keeps_date(self) -> None:
        command = rebuild_command(_Window().pending_thought, "Nie, jednak o 19")
        self.assertIn("2026-07-28", command)
        self.assertIn("o 19", command)
        self.assertNotIn("o 18", command)

    def test_revision_replans_instead_of_cancelling(self) -> None:
        window = _Window()
        handle_owner_confirmation(window, "Nie, jednak o 19")
        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.brain.executed, [])
        self.assertEqual(len(window.replanned), 1)
        self.assertIn("o 19", window.replanned[0][0])
        self.assertFalse(any("Anulowano" in line for line in window.console_page.lines))

    def test_plain_no_cancels(self) -> None:
        window = _Window()
        handle_owner_confirmation(window, "nie")
        self.assertIsNone(window.pending_thought)
        self.assertTrue(any("Anulowano" in line for line in window.console_page.lines))

    def test_yes_executes_once(self) -> None:
        window = _Window()
        handle_owner_confirmation(window, "tak")
        self.assertIsNone(window.pending_thought)
        self.assertEqual(len(window.brain.executed), 1)

    def test_main_window_delegates_to_shared_safe_handler(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/main_window.py").read_text(encoding="utf-8")
        method = source.split("def handle_confirmation", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("super().handle_confirmation(answer)", method)
        self.assertIn("handle_owner_confirmation(self, answer)", method)
        self.assertNotIn("self.brain.execute(", method)

    def test_source_limits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/main_window.py": 440,
            "app/gui/business_command_runtime.py": 180,
            "app/gui/confirmation_revision_runtime.py": 100,
            "app/natural_actions/revisions.py": 180,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

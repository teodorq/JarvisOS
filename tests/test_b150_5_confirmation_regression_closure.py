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


class B1505ConfirmationRegressionClosureTests(unittest.TestCase):
    def test_compound_no_is_revision(self) -> None:
        self.assertEqual(classify_confirmation("Nie, jednak o 19").kind, "revise")

    def test_revision_replans_and_keeps_date(self) -> None:
        window = _Window()
        command = rebuild_command(window.pending_thought, "Nie, jednak o 19")
        self.assertIn("2026-07-28", command)
        self.assertIn("o 19", command)
        handle_owner_confirmation(window, "Nie, jednak o 19")
        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.brain.executed, [])
        self.assertEqual(len(window.replanned), 1)

    def test_plain_no_cancels_and_yes_executes_once(self) -> None:
        no_window = _Window()
        handle_owner_confirmation(no_window, "nie")
        self.assertTrue(any("Anulowano" in line for line in no_window.console_page.lines))
        yes_window = _Window()
        handle_owner_confirmation(yes_window, "tak")
        self.assertEqual(len(yes_window.brain.executed), 1)

    def test_main_window_preserves_safe_shared_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/main_window.py").read_text(encoding="utf-8")
        method = source.split("def handle_confirmation", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("super().handle_confirmation(answer)", method)
        self.assertIn("handle_owner_confirmation(self, answer)", method)
        self.assertNotIn("self.brain.execute(", method)
        self.assertLess(len(source.splitlines()), 440)

    def test_all_installer_regression_modules_are_packaged(self) -> None:
        root = Path(__file__).resolve().parents[1]
        required = [
            "tests/test_b146_b150_contextual_productivity.py",
            "tests/test_b150_1_confirmation_revision_input.py",
            "tests/test_b150_2_owner_confirmation_revision.py",
            "tests/test_b150_3_confirmation_actual_runtime.py",
            "tests/test_b150_4_confirmation_compatibility.py",
        ]
        self.assertEqual([path for path in required if not (root / path).is_file()], [])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import unittest

from app.gui.confirmation_revision_runtime import handle_owner_confirmation
from app.natural_actions.revisions import rebuild_command
from app.natural_actions.validation import classify_confirmation


class _Console:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.states: list[tuple[str, str]] = []

    def append(self, text: str) -> None:
        self.lines.append(text)

    def set_state(self, text: str, kind: str) -> None:
        self.states.append((text, kind))


class _Brain:
    def __init__(self) -> None:
        self.executed: list[dict] = []

    def execute(self, thought: dict) -> str:
        self.executed.append(dict(thought))
        return "Wykonano"


class _Window:
    def __init__(self) -> None:
        self.pending_thought = {
            "assistant_intent": "calendar_create",
            "natural_slots": {
                "title": "trening",
                "when": "2026-07-22T18:00:00+02:00",
                "duration_minutes": 60,
            },
        }
        self.console_page = _Console()
        self.brain = _Brain()
        self.spoken: list[str] = []
        self.replanned: list[tuple[str, str]] = []

    def say_safe(self, text: str) -> None:
        self.spoken.append(text)

    def process_command(self, text: str, source: str = "Ty") -> None:
        self.replanned.append((text, source))


class B1502OwnerConfirmationRevisionTests(unittest.TestCase):
    def test_compound_negative_correction_is_revision_not_rejection(self) -> None:
        decision = classify_confirmation("Nie, jednak o 19")
        self.assertEqual(decision.kind, "revise")

    def test_calendar_revision_replaces_time_and_removes_discourse_words(self) -> None:
        thought = _Window().pending_thought
        command = rebuild_command(thought, "Nie, jednak o 19")
        self.assertIn("o 19", command)
        self.assertNotIn("jednak", command.casefold())
        self.assertNotIn("o 18", command)

    def test_owner_revision_replans_instead_of_cancelling(self) -> None:
        window = _Window()
        handle_owner_confirmation(window, "Nie, jednak o 19")
        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.brain.executed, [])
        self.assertEqual(len(window.replanned), 1)
        self.assertIn("o 19", window.replanned[0][0])
        self.assertFalse(any("Anulowano" in line for line in window.console_page.lines))

    def test_plain_no_still_cancels(self) -> None:
        window = _Window()
        handle_owner_confirmation(window, "nie")
        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.replanned, [])
        self.assertTrue(any("Anulowano" in line for line in window.console_page.lines))

    def test_yes_still_executes_once(self) -> None:
        window = _Window()
        handle_owner_confirmation(window, "tak")
        self.assertIsNone(window.pending_thought)
        self.assertEqual(len(window.brain.executed), 1)
        self.assertEqual(window.replanned, [])

    def test_owner_runtimes_delegate_to_shared_handler(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "app/gui/main_window.py",
            "app/gui/business_command_runtime.py",
        ):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertIn("handle_owner_confirmation(self, answer)", source)


if __name__ == "__main__":
    unittest.main()

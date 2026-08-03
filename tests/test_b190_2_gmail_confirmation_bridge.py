from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.gui.confirmed_calendar_execution import execute_confirmed_calendar_plan
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from tests.test_b186_b190_gmail_live_workflow import FakeOnline
from tests.test_b151_b155_daily_actions import FakeOnline as LegacyFakeOnline


class _Assistant:
    def __init__(self, natural_actions):
        self.natural_actions = natural_actions


class _BrainMustNotExecute:
    def execute(self, _thought):
        raise AssertionError("Exact Gmail send must use the shared assistant bridge.")


class _Window:
    def __init__(self, service):
        self.assistant = _Assistant(service)
        self.brain = _BrainMustNotExecute()


class B1902GmailConfirmationBridgeTests(unittest.TestCase):
    def prepared(self, directory: str):
        online = FakeOnline(directory)
        service = NaturalActionService(directory, online=online)
        service.handle("Znajdź ostatnią wiadomość od anna@example.com")
        reply = service.plan("Przygotuj odpowiedź: Dziękuję, odezwę się jutro.")
        PlannedNaturalActionExecutor.execute(_Assistant(service), reply)
        return online, service, _Window(service)

    def test_exact_client_phrase_is_forced_to_confirmed_gmail_send(self) -> None:
        with TemporaryDirectory() as directory:
            _online, _service, window = self.prepared(directory)
            thought = active_resolution_priority_thought(
                window, "Wyślij tę odpowiedź."
            )
        self.assertIsNotNone(thought)
        self.assertEqual(thought["assistant_intent"], "mail_send_existing")
        self.assertTrue(thought["requires_confirmation"])
        self.assertIn("Wysłać przygotowaną odpowiedź", thought["confirmation_message"])

    def test_shared_assistant_executes_confirmed_send_and_verifies_gmail(self) -> None:
        with TemporaryDirectory() as directory:
            online, _service, window = self.prepared(directory)
            thought = active_resolution_priority_thought(window, "Wyślij tę odpowiedź")
            response = execute_confirmed_calendar_plan(window, thought)
        self.assertEqual(online.provider.sent, ["draft-reply-1"])
        self.assertIn("sprawdzony w Gmail", response)

    def test_common_natural_variants_use_the_same_safe_plan(self) -> None:
        variants = (
            "Wyślij tą odpowiedź", "Wyślij przygotowaną odpowiedź",
            "Wyślij przygotowany szkic", "Nadaj tę odpowiedź",
        )
        for phrase in variants:
            with self.subTest(phrase=phrase), TemporaryDirectory() as directory:
                _online, _service, window = self.prepared(directory)
                thought = active_resolution_priority_thought(window, phrase)
                self.assertIsNotNone(thought)
                self.assertEqual(thought["assistant_intent"], "mail_send_existing")
                self.assertTrue(thought["requires_confirmation"])

    def test_no_draft_does_not_create_false_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            service = NaturalActionService(directory, online=FakeOnline(directory))
            thought = active_resolution_priority_thought(
                _Window(service), "Wyślij tę odpowiedź"
            )
        self.assertIsNone(thought)

    def test_legacy_local_draft_wins_over_stale_live_draft(self) -> None:
        with TemporaryDirectory() as directory:
            online = LegacyFakeOnline(directory)
            service = NaturalActionService(directory, online=online)
            service.handle("Napisz Pawłowi, że raport jest gotowy")
            plan = service.plan("Wyślij ten szkic")
            response = service.handle("Wyślij ten szkic")
        self.assertEqual(plan["natural_slots"]["draft_id"], "draft-1")
        self.assertEqual(online.gmail.sent, ["draft-1"])
        self.assertIn("ostatni szkic", response.lower())

    def test_runtime_files_keep_historical_bounds_and_priority_hook(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/active_resolution_priority.py": 80,
            "app/gui/confirmed_calendar_execution.py": 80,
            "app/natural_actions/advanced_understanding.py": 220,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:\\JarvisAI", source)
        for relative in (
            "app/gui/client_command_runtime.py",
            "app/gui/business_command_runtime.py",
        ):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertIn("active_resolution_priority_thought", source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sys
import types
import unittest

try:
    from app.gui.client_command_runtime import ClientCommandRuntimeMixin
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    qtcore = types.ModuleType("PySide6.QtCore")

    class _QTimer:
        @staticmethod
        def singleShot(_delay, callback):
            callback()

    qtcore.QTimer = _QTimer
    package = types.ModuleType("PySide6")
    package.QtCore = qtcore
    sys.modules["PySide6"] = package
    sys.modules["PySide6.QtCore"] = qtcore
    from app.gui.client_command_runtime import ClientCommandRuntimeMixin
from app.natural_actions.revisions import rebuild_command
from app.natural_actions.service import NaturalActionService
from app.natural_actions.temporal import PolishTemporalParser
from app.natural_actions.understanding import NaturalActionUnderstanding
from app.natural_actions.validation import (
    classify_confirmation,
    is_placeholder,
)


FIXED_NOW = datetime(2026, 7, 20, 12, 0).astimezone()


class FakeProvider:
    def __init__(self) -> None:
        self.messages = [
            {
                "from": "Paweł Kowalski <pawel@example.com>",
                "to": "Kacper <kacper@example.com>",
            }
        ]

    def list_gmail_messages(self, **_kwargs):
        return list(self.messages)


class FakeGmail:
    def __init__(self) -> None:
        self.drafts = []
        self.sent = []

    def create_draft(self, recipient, subject, body):
        self.drafts.append((recipient, subject, body))
        return {"draft_id": f"draft-{len(self.drafts)}"}

    def send_draft(self, draft_id):
        self.sent.append(draft_id)
        return {"message_id": f"message-{len(self.sent)}"}


class FakeCalendar:
    def __init__(self) -> None:
        self.events = []

    def create_event(self, title, when, **kwargs):
        self.events.append((title, when, kwargs))
        return {"event_id": f"event-{len(self.events)}"}


class FakeOnline:
    def __init__(self) -> None:
        self.provider = FakeProvider()
        self.gmail = FakeGmail()
        self.calendar = FakeCalendar()


class DummyClientRuntime(ClientCommandRuntimeMixin):
    def __init__(self, thought) -> None:
        self.pending_thought = thought
        self.events = []
        self.spoken = []
        self.replanned = []

    def _publish_client_event(self, **event) -> None:
        self.events.append(event)

    def say_safe(self, value) -> None:
        self.spoken.append(value)

    def process_client_command(self, value) -> None:
        self.replanned.append(value)


class B146B150ContextualProductivityTests(unittest.TestCase):
    def service(self, directory: str, online: FakeOnline | None = None):
        return NaturalActionService(
            directory,
            online=online or FakeOnline(),
            now_provider=lambda: FIXED_NOW,
        )

    def test_b146_reuses_last_mail_recipient_for_pronoun(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            service.handle("Napisz Pawłowi, że dokument jest gotowy")
            plan = service.plan("Napisz mu też, że jutro zadzwonię")
        self.assertTrue(plan["used_context"])
        self.assertEqual(plan["natural_slots"]["recipient_email"], "pawel@example.com")
        self.assertEqual(plan["natural_slots"]["body"], "jutro zadzwonię")
        self.assertTrue(plan["requires_confirmation"])

    def test_b146_reuses_previous_calendar_time_on_new_date(self) -> None:
        online = FakeOnline()
        with TemporaryDirectory() as directory:
            service = self.service(directory, online)
            service.handle("Dodaj trening jutro o 18")
            plan = service.plan(
                "Dodaj siłownię pojutrze o tej samej porze"
            )
        when = datetime.fromisoformat(plan["natural_slots"]["when"])
        self.assertEqual((when.year, when.month, when.day), (2026, 7, 22))
        self.assertEqual((when.hour, when.minute), (18, 0))
        self.assertTrue(plan["used_context"])

    def test_b147_rejects_placeholder_recipient(self) -> None:
        with TemporaryDirectory() as directory:
            plan = self.service(directory).plan(
                "Napisz email do [imię lub adres], że jutro będę później"
            )
        self.assertTrue(plan["read_only"])
        self.assertIn("Podaj imię kontaktu", plan["clarification"])
        self.assertTrue(is_placeholder("[imię lub adres]"))

    def test_b147_learns_alias_after_email_clarification(self) -> None:
        online = FakeOnline()
        online.provider.messages = []
        with TemporaryDirectory() as directory:
            service = self.service(directory, online)
            first = service.handle(
                "Napisz Pawłowi, że dokument jest gotowy"
            )
            self.assertIn("Podaj adres e-mail", first)
            service.handle("pawel@example.com")
            plan = service.plan(
                "Napisz Pawłowi, że drugi dokument jest gotowy"
            )
        self.assertEqual(plan["natural_slots"]["recipient_email"], "pawel@example.com")
        self.assertTrue(plan["requires_confirmation"])

    def test_b148_calendar_revision_preserves_date_and_reminder(self) -> None:
        thought = {
            "assistant_intent": "calendar_create",
            "natural_slots": {
                "title": "trening",
                "when": "2026-07-21T18:00:00+02:00",
                "duration_minutes": 60,
                "reminder_minutes": 20,
            },
        }
        command = rebuild_command(thought, "nie, jednak o 19")
        request = NaturalActionUnderstanding(
            PolishTemporalParser(lambda: FIXED_NOW)
        ).parse(command)
        when = datetime.fromisoformat(request.slots["when"])
        self.assertEqual((when.year, when.month, when.day), (2026, 7, 21))
        self.assertEqual((when.hour, when.minute), (19, 0))
        self.assertEqual(request.slots["reminder_minutes"], 20)

    def test_b148_mail_revision_changes_recipient_only(self) -> None:
        thought = {
            "assistant_intent": "mail_draft",
            "natural_slots": {
                "recipient_ref": "Paweł",
                "recipient_email": "pawel@example.com",
                "subject": "Spotkanie",
                "body": "Będę później",
            },
        }
        command = rebuild_command(thought, "nie, do jan@example.com")
        self.assertIn("jan@example.com", command)
        self.assertIn("Będę później", command)

    def test_b148_client_confirmation_accepts_revision_instead_of_cancel(self) -> None:
        thought = {
            "assistant_intent": "calendar_create",
            "natural_slots": {
                "title": "trening",
                "when": "2026-07-21T18:00:00+02:00",
                "duration_minutes": 60,
            },
        }
        runtime = DummyClientRuntime(thought)
        with patch(
            "app.gui.client_command_runtime.QTimer.singleShot",
            side_effect=lambda _delay, callback: callback(),
        ):
            runtime._handle_client_confirmation("nie, jednak o 19")
        self.assertIsNone(runtime.pending_thought)
        self.assertEqual(len(runtime.replanned), 1)
        self.assertIn("o 19", runtime.replanned[0])
        self.assertEqual(runtime.events[-1]["state"], "thinking")

    def test_b149_same_action_is_executed_only_once(self) -> None:
        online = FakeOnline()
        with TemporaryDirectory() as directory:
            service = self.service(directory, online)
            first = service.handle(
                "Napisz email do pawel@example.com, że dokument jest gotowy"
            )
            second = service.handle(
                "Napisz email do pawel@example.com, że dokument jest gotowy"
            )
        self.assertIn("Szkic", first)
        self.assertIn("już wykonane", second)
        self.assertEqual(len(online.gmail.drafts), 1)

    def test_b150_understands_spoken_hour_and_reminder_words(self) -> None:
        parser = PolishTemporalParser(lambda: FIXED_NOW)
        when = parser.parse_when(
            "Dodaj jutro trening o osiemnastej"
        )
        reminder = parser.reminder_minutes(
            "przypomnij mi dwadzieścia minut wcześniej"
        )
        self.assertIsNotNone(when)
        self.assertEqual((when.hour, when.minute), (18, 0))
        self.assertEqual(reminder, 20)

    def test_b150_surprise_phrasings_route_without_exact_commands(self) -> None:
        understanding = NaturalActionUnderstanding(
            PolishTemporalParser(lambda: FIXED_NOW)
        )
        examples = {
            "Skrobnij Pawłowi, że raport jest gotowy": "mail_draft",
            "Podeślij do biuro@example.com wiadomość, że ruszamy": "mail_send",
            "Zaklep mi lekarza w piątek o dziewiątej": "calendar_create",
            "Jutro wieczorem mam siłownię, wpisz ją": "calendar_create",
            "Wrzuć trening na jutro na 18:30": "calendar_create",
        }
        for command, expected in examples.items():
            with self.subTest(command=command):
                self.assertEqual(
                    understanding.parse(command).intent,
                    expected,
                )

    def test_confirmation_language_is_not_limited_to_one_word(self) -> None:
        for value in ("tak", "jasne", "dobrze", "możesz", "potwierdzam"):
            self.assertEqual(classify_confirmation(value).kind, "accept")
        for value in ("nie", "anuluj", "nieważne"):
            self.assertEqual(classify_confirmation(value).kind, "reject")
        self.assertEqual(
            classify_confirmation("nie, jednak o 19").kind,
            "revise",
        )

    def test_stage_status_and_source_limits(self) -> None:
        with TemporaryDirectory() as directory:
            status = self.service(directory).status()
        self.assertTrue(all(
            stage in status["stages"]
            for stage in ("B146", "B147", "B148", "B149", "B150")
        ))
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/service.py": 320,
            "app/natural_actions/understanding.py": 300,
            "app/gui/client_command_runtime.py": 180,
            "app/natural_actions/revisions.py": 180,
            "app/natural_actions/validation.py": 120,
            "app/natural_actions/runtime.py": 140,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

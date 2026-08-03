from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.gui.voice_command_dispatch import dispatch_voice_text
from app.jarvis_experience.smart_task_loop import SmartTaskLoop
from app.natural_actions.service import NaturalActionService
from app.natural_actions.temporal import PolishTemporalParser
from app.natural_actions.understanding import NaturalActionUnderstanding


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


class B141B145NaturalActionsTests(unittest.TestCase):
    def understanding(self) -> NaturalActionUnderstanding:
        return NaturalActionUnderstanding(
            PolishTemporalParser(lambda: FIXED_NOW)
        )

    def service(self, directory: str, online: FakeOnline | None = None):
        return NaturalActionService(
            directory,
            online=online or FakeOnline(),
            now_provider=lambda: FIXED_NOW,
        )

    def test_mail_intent_generalizes_across_wording(self) -> None:
        examples = (
            "Napisz email do pawel@example.com, że będę później",
            "Przygotuj wiadomość do Pawła o treści jutro zadzwonię",
            "Skrobnij mail do ani@example.com: treść dokument jest gotowy",
            "Wyślij do biuro@example.com wiadomość: przyjadę o dziewiątej",
            "Podeślij e-mail do jan@example.com o treści wszystko działa",
            "Napisz Pawłowi, że dokument jest gotowy",
        )
        intents = [self.understanding().parse(value).intent for value in examples]
        self.assertEqual(intents[:3], ["mail_draft"] * 3)
        self.assertEqual(intents[3:5], ["mail_send"] * 2)
        self.assertEqual(intents[5], "mail_draft")


    def test_direct_dative_recipient_is_understood_without_fixed_phrase(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            plan = service.plan("Napisz Pawłowi, że dokument jest gotowy")
        self.assertEqual(plan["assistant_intent"], "mail_draft")
        self.assertEqual(plan["natural_slots"]["recipient_ref"], "Pawłowi")
        self.assertEqual(plan["natural_slots"]["recipient_email"], "pawel@example.com")
        self.assertTrue(plan["requires_confirmation"])

    def test_calendar_intent_generalizes_across_wording(self) -> None:
        examples = (
            "Dodaj jutro trening o 18",
            "Jutro o 18 mam trening",
            "Wrzuć do kalendarza wizytę w piątek o 9:30",
            "Zaklep spotkanie z Pawłem na 22.07 o 14",
            "Wieczorem wpisz mi siłownię i przypomnij pół godziny wcześniej",
        )
        self.assertTrue(all(
            self.understanding().parse(value).intent == "calendar_create"
            for value in examples
        ))

    def test_calendar_extracts_time_duration_and_reminder(self) -> None:
        request = self.understanding().parse(
            "Wpisz trening jutro o 18:15 na 2 godziny i przypomnij 20 minut wcześniej"
        )
        self.assertEqual(request.slots["title"], "trening")
        expected_when = FIXED_NOW.replace(
            year=2026, month=7, day=21, hour=18, minute=15,
            second=0, microsecond=0,
        ).isoformat()
        self.assertEqual(request.slots["when"], expected_when)
        self.assertEqual(request.slots["duration_minutes"], 120)
        self.assertEqual(request.slots["reminder_minutes"], 20)

    def test_mail_extracts_recipient_body_and_generated_subject(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            plan = service.plan(
                "Napisz email do pawel@example.com o treści: jutro będę godzinę później"
            )
        self.assertFalse(plan["read_only"])
        self.assertEqual(plan["natural_slots"]["recipient_email"], "pawel@example.com")
        self.assertEqual(plan["natural_slots"]["body"], "jutro będę godzinę później")
        self.assertIn("jutro będę", plan["natural_slots"]["subject"])
        self.assertIn("Przygotować szkic", plan["confirmation_message"])

    def test_name_is_resolved_from_recent_gmail_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            plan = service.plan(
                "Przygotuj wiadomość do Pawła, że dokument jest gotowy"
            )
        self.assertEqual(plan["natural_slots"]["recipient_email"], "pawel@example.com")
        self.assertFalse(plan["read_only"])

    def test_missing_calendar_time_uses_multi_turn_context(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            response = service.handle("Dodaj mi trening jutro")
            self.assertIn("Kiedy dokładnie", response)
            self.assertTrue(service.has_pending())
            plan = service.plan("O 18 i przypomnij 20 minut wcześniej")
            self.assertFalse(plan["read_only"])
            self.assertIn("18:00", plan["confirmation_message"])
            response = service.handle("O 18 i przypomnij 20 minut wcześniej")
            self.assertIn("Dodałem", response)
            self.assertFalse(service.has_pending())

    def test_missing_email_address_can_be_completed_in_next_turn(self) -> None:
        online = FakeOnline()
        online.provider.messages = []
        with TemporaryDirectory() as directory:
            service = self.service(directory, online)
            response = service.handle(
                "Przygotuj wiadomość do Pawła, że jutro przyjadę później"
            )
            self.assertIn("Podaj adres e-mail", response)
            plan = service.plan("pawel@example.com")
            self.assertFalse(plan["read_only"])
            response = service.handle("pawel@example.com")
            self.assertIn("Szkic", response)
            self.assertEqual(online.gmail.drafts[0][0], "pawel@example.com")

    def test_draft_send_and_calendar_use_real_action_adapters(self) -> None:
        online = FakeOnline()
        with TemporaryDirectory() as directory:
            service = self.service(directory, online)
            draft = service.handle(
                "Napisz email do pawel@example.com, że będę o dziewiątej"
            )
            sent = service.handle(
                "Wyślij email do pawel@example.com o treści dokument jest gotowy"
            )
            event = service.handle(
                "Dodaj jutro trening o 18 i przypomnij 20 minut wcześniej"
            )
        self.assertIn("Szkic", draft)
        self.assertIn("wysłana", sent)
        self.assertEqual(len(online.gmail.drafts), 2)
        self.assertEqual(online.gmail.sent, ["draft-2"])
        self.assertIn("Dodałem", event)
        self.assertEqual(online.calendar.events[0][2]["reminder_minutes"], 20)

    def test_smart_task_loop_uses_action_specific_confirmation(self) -> None:
        class Brain:
            def think(self, _command):
                return {
                    "can_execute": True,
                    "handler": "personal_assistant",
                    "read_only": False,
                    "confirmation_message": "Dodać trening jutro o 18:00?",
                }

        outcome = SmartTaskLoop(
            Brain(), lambda *_args: {"allowed": True}, lambda _thought: False
        ).plan("dodaj trening")
        self.assertEqual(outcome.status, "CONFIRM")
        self.assertEqual(outcome.message, "Dodać trening jutro o 18:00?")

    def test_voice_dispatch_keeps_client_commands_out_of_owner_console(self) -> None:
        calls = []
        client = SimpleNamespace(
            isVisible=lambda: True,
            controller=SimpleNamespace(status=lambda: {"runtime": {"mode": "CLIENT"}}),
        )
        window = SimpleNamespace(
            client_window=client,
            process_client_command=lambda value: calls.append(("client", value)),
            process_command=lambda *args, **kwargs: calls.append(("owner", args, kwargs)),
            console_page=SimpleNamespace(append=lambda _text: None, set_state=lambda *_args: None),
        )
        dispatch_voice_text(window, "Dodaj jutro trening o 18")
        self.assertEqual(calls, [("client", "Dodaj jutro trening o 18")])

    def test_source_limits_and_no_hardcoded_project_path(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/assistant/controller.py": 480,
            "app/gui/business_command_runtime.py": 180,
            "app/gui/client_experience_window.py": 440,
            "app/online_assistant/google_workspace.py": 480,
            "app/voice/voice_listener.py": 220,
            "app/natural_actions/service.py": 320,
            "app/natural_actions/understanding.py": 300,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

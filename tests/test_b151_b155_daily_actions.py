from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.service import NaturalActionService
from app.natural_actions.temporal import PolishTemporalParser
from app.natural_actions.understanding import NaturalActionUnderstanding
from app.online_assistant.calendar_center import GoogleCalendarCenter


FIXED_NOW = datetime(2026, 7, 27, 12, 0).astimezone()


class FakeProvider:
    def __init__(self) -> None:
        self.events = [
            {
                "id": "event-training",
                "title": "trening",
                "start_at": FIXED_NOW.replace(day=28, hour=18).isoformat(),
                "end_at": FIXED_NOW.replace(day=28, hour=19).isoformat(),
                "location": "",
                "status": "confirmed",
                "html_link": "",
            },
            {
                "id": "event-plumber",
                "title": "spotkanie z hydraulikiem",
                "start_at": FIXED_NOW.replace(day=29, hour=9).isoformat(),
                "end_at": FIXED_NOW.replace(day=29, hour=10).isoformat(),
                "location": "",
                "status": "confirmed",
                "html_link": "",
            },
        ]
        self.updated = []
        self.deleted = []
        self.messages = [
            {"from": "Paweł <pawel@example.com>", "to": "Kacper <k@example.com>"}
        ]

    def list_calendar_events(self, **kwargs):
        start = kwargs["start_at"]
        end = kwargs["end_at"]
        return [
            item for item in self.events
            if start <= datetime.fromisoformat(item["start_at"]) < end
        ]

    def update_calendar_event(self, event_id, **kwargs):
        self.updated.append((event_id, kwargs))
        start = kwargs["start_at"]
        return {
            "event_id": event_id,
            "title": kwargs["title"],
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(minutes=kwargs["duration_minutes"])).isoformat(),
        }

    def delete_calendar_event(self, event_id):
        self.deleted.append(event_id)
        return {"event_id": event_id}

    def list_gmail_messages(self, **_kwargs):
        return list(self.messages)


class FakeGmail:
    def __init__(self) -> None:
        self.drafts = []
        self.sent = []
        self.history_draft = {}

    def create_draft(self, recipient, subject, body):
        result = {
            "draft_id": f"draft-{len(self.drafts) + 1}",
            "recipient": recipient,
            "subject": subject,
        }
        self.drafts.append((recipient, subject, body, result["draft_id"]))
        self.history_draft = result
        return result

    def send_draft(self, draft_id):
        self.sent.append(draft_id)
        return {"message_id": "message-1"}

    def last_draft(self):
        return dict(self.history_draft)


class FakeCalendar(GoogleCalendarCenter):
    pass


class FakeOnline:
    def __init__(self, directory: str) -> None:
        self.provider = FakeProvider()
        self.gmail = FakeGmail()
        self.calendar = FakeCalendar(directory, provider=self.provider)


class B151B155DailyActionsTests(unittest.TestCase):
    def understanding(self) -> NaturalActionUnderstanding:
        return NaturalActionUnderstanding(PolishTemporalParser(lambda: FIXED_NOW))

    def service(self, directory: str, online: FakeOnline | None = None):
        return NaturalActionService(
            directory,
            online=online or FakeOnline(directory),
            now_provider=lambda: FIXED_NOW,
        )

    def test_b151_update_event_is_found_and_requires_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            plan = service.plan("Przenieś jutrzejszy trening na 20")
        self.assertEqual(plan["assistant_intent"], "calendar_update")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("20:00", plan["confirmation_message"])
        self.assertEqual(plan["natural_slots"]["event_id"], "event-training")

    def test_b151_confirmed_update_uses_existing_duration(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            response = service.handle("Przenieś jutrzejszy trening na 20")
        self.assertIn("Przeniosłem", response)
        event_id, kwargs = online.provider.updated[0]
        self.assertEqual(event_id, "event-training")
        self.assertEqual(kwargs["duration_minutes"], 60)
        self.assertEqual(kwargs["start_at"].hour, 20)

    def test_b151_delete_event_requires_confirmation_and_executes_once(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            plan = service.plan("Usuń spotkanie z hydraulikiem")
            first = service.handle("Usuń spotkanie z hydraulikiem")
            second = service.handle("Usuń spotkanie z hydraulikiem")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("Usunąłem", first)
        self.assertIn("już wykonane", second)
        self.assertEqual(online.provider.deleted, ["event-plumber"])

    def test_b152_search_handles_inflected_title_and_date(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            plan = service.plan("Pokaż jutrzejszy trening")
            response = service.handle("Pokaż jutrzejszy trening")
        self.assertTrue(plan["read_only"])
        self.assertFalse(plan["requires_confirmation"])
        self.assertIn("trening", response)

    def test_b153_send_this_draft_uses_existing_draft_only_after_gate(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Napisz Pawłowi, że raport jest gotowy")
            plan = service.plan("Wyślij ten szkic")
            response = service.handle("Wyślij ten szkic")
        self.assertEqual(plan["assistant_intent"], "mail_send_existing")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("ostatni szkic", response.lower())
        self.assertEqual(online.gmail.sent, ["draft-1"])
        self.assertEqual(len(online.gmail.drafts), 1)

    def test_b154_write_again_reuses_same_contact_and_asks_for_body(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            service.handle("Napisz Pawłowi, że raport jest gotowy")
            response = service.handle("Napisz ponownie do tej samej osoby")
            plan = service.plan("że zadzwonię rano")
        self.assertIn("Co ma zawierać", response)
        self.assertEqual(plan["natural_slots"]["recipient_email"], "pawel@example.com")
        self.assertEqual(plan["natural_slots"]["body"], "zadzwonię rano")

    def test_b155_surprise_phrasings_are_semantic_not_fixed(self) -> None:
        examples = {
            "Przesuń siłownię z jutra na dwudziestą": "calendar_update",
            "Skasuj wizytę u lekarza": "calendar_delete",
            "Kiedy mam najbliższy trening?": "calendar_search",
            "Nadaj ostatni szkic": "mail_send_existing",
            "Napisz ponownie do tej samej osoby": "mail_draft",
        }
        for command, intent in examples.items():
            with self.subTest(command=command):
                self.assertEqual(self.understanding().parse(command).intent, intent)

    def test_stage_status_and_source_limits(self) -> None:
        with TemporaryDirectory() as directory:
            stages = self.service(directory).status()["stages"]
        self.assertEqual(stages["B151"], "CALENDAR_EVENT_MUTATION_READY")
        self.assertEqual(stages["B155"], "DAILY_ACTION_SURPRISE_GATES_READY")
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/service.py": 320,
            "app/natural_actions/understanding.py": 300,
            "app/natural_actions/runtime.py": 140,
            "app/online_assistant/google_workspace.py": 480,
            "app/online_assistant/calendar_center.py": 190,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

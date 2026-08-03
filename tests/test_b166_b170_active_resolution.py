from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.service import NaturalActionService


class FakeProvider:
    pass


class FakeCalendar:
    def __init__(self, events):
        self.events = [dict(item) for item in events]
        self.updated = []

    def find_events(self, _query, *, start_at, end_at, max_results=20):
        return [
            dict(item) for item in self.events
            if start_at <= datetime.fromisoformat(item["start_at"]) < end_at
        ][:max_results]

    def update_event(
        self,
        event_id,
        title,
        start_at,
        *,
        duration_minutes=60,
        reminder_minutes=None,
    ):
        self.updated.append({
            "event_id": event_id,
            "title": title,
            "start_at": start_at,
            "duration_minutes": duration_minutes,
            "reminder_minutes": reminder_minutes,
        })
        end = start_at + timedelta(minutes=duration_minutes)
        for item in self.events:
            if item["id"] == event_id:
                item["start_at"] = start_at.isoformat()
                item["end_at"] = end.isoformat()
        return {
            "event_id": event_id,
            "title": title,
            "start_at": start_at.isoformat(),
            "end_at": end.isoformat(),
        }


class FakeGmail:
    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.drafts = []

    def priority(self, _limit=5):
        return [dict(item) for item in self.messages]

    def create_draft(self, recipient, subject, body):
        draft_id = f"draft-{len(self.drafts) + 1}"
        self.drafts.append((recipient, subject, body, draft_id))
        return {"draft_id": draft_id, "recipient": recipient, "subject": subject}

    def last_draft(self):
        if not self.drafts:
            return {}
        recipient, subject, _body, draft_id = self.drafts[-1]
        return {"recipient": recipient, "subject": subject, "draft_id": draft_id}


class FakeReminders:
    def __init__(self, due=0, text=""):
        self.due = due
        self.text = text

    def status(self):
        result = {"due_count": self.due, "pending_count": self.due}
        if self.text:
            result["next_reminder"] = {"text": self.text, "due_at": ""}
        return result


class FakeOnline:
    def __init__(self, root, *, events=None, mail=None, due=0, reminder=""):
        self.project_root = Path(root)
        self.provider = FakeProvider()
        self.calendar = FakeCalendar(events or [])
        self.gmail = FakeGmail(mail)
        self.reminders = FakeReminders(due, reminder)


class B166B170ActiveResolutionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now().astimezone().replace(microsecond=0)
        start = (self.now + timedelta(days=1)).replace(hour=18, minute=0)
        self.events = [
            {
                "id": "event-a",
                "title": "Spotkanie A",
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(hours=1)).isoformat(),
            },
            {
                "id": "event-b",
                "title": "Spotkanie B",
                "start_at": (start + timedelta(minutes=45)).isoformat(),
                "end_at": (start + timedelta(minutes=105)).isoformat(),
            },
        ]
        self.mail = [{
            "id": "mail-1",
            "thread_id": "thread-1",
            "from": "Anna Kowalska <anna@example.com>",
            "subject": "Termin odbioru",
            "snippet": "Czy potwierdzasz jutrzejszy termin?",
            "important": True,
            "unread": True,
        }]

    def service(self, directory, **kwargs):
        online = FakeOnline(directory, **kwargs)
        return NaturalActionService(directory, online=online), online

    def test_b166_advice_proposes_safe_resolution_without_write(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, events=self.events)
            plan = service.plan("Co mam zrobić z tym konfliktem?")
            response = service.handle("Co mam zrobić z tym konfliktem?")
        self.assertEqual(plan["assistant_intent"], "active_conflict_advice")
        self.assertTrue(plan["read_only"])
        self.assertFalse(plan["requires_confirmation"])
        self.assertIn("Spotkanie B", response)
        self.assertIn("19:00", response)
        self.assertEqual(online.calendar.updated, [])

    def test_b167_apply_proposal_requires_confirmation_and_preserves_duration(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, events=self.events)
            service.handle("Co mam zrobić z tym konfliktem?")
            plan = service.plan("Zrób to")
            response = service.handle("Zrób to")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("Spotkanie B", plan["confirmation_message"])
        self.assertIn("Przeniosłem", response)
        self.assertIn("Sprawdziłem nowy termin", response)
        self.assertEqual(len(online.calendar.updated), 1)
        self.assertEqual(online.calendar.updated[0]["duration_minutes"], 60)
        self.assertEqual(online.calendar.updated[0]["start_at"].hour, 19)

    def test_b167_explicit_second_event_move_uses_requested_hour(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, events=self.events)
            plan = service.plan("Przenieś drugie spotkanie z konfliktu na 20")
            response = service.handle("Przenieś drugie spotkanie z konfliktu na 20")
        self.assertEqual(plan["assistant_intent"], "active_conflict_move")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("20:00", plan["confirmation_message"])
        self.assertIn("20:00", response)
        self.assertEqual(online.calendar.updated[0]["event_id"], "event-b")

    def test_b168_reply_to_important_mail_creates_draft_only(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, mail=self.mail)
            plan = service.plan(
                "Odpisz na tę wiadomość, że potwierdzam termin"
            )
            response = service.handle(
                "Odpisz na tę wiadomość, że potwierdzam termin"
            )
        self.assertEqual(plan["assistant_intent"], "active_mail_reply")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("Anna Kowalska", plan["confirmation_message"])
        self.assertIn("nie została wysłana", response)
        self.assertEqual(len(online.gmail.drafts), 1)
        recipient, subject, body, _draft_id = online.gmail.drafts[0]
        self.assertEqual(recipient, "anna@example.com")
        self.assertEqual(subject, "Re: Termin odbioru")
        self.assertEqual(body, "potwierdzam termin")

    def test_b168_missing_reply_body_asks_only_for_content(self):
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory, mail=self.mail)
            response = service.handle("Odpisz na tę wiadomość")
            plan = service.plan("że będę o osiemnastej")
        self.assertIn("Co mam napisać", response)
        self.assertEqual(plan["assistant_intent"], "active_mail_reply")
        self.assertEqual(plan["natural_slots"]["body"], "będę o osiemnastej")
        self.assertTrue(plan["requires_confirmation"])

    def test_b169_snooze_suppresses_and_then_releases_alert(self):
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory, events=self.events)
            first = service.startup_brief(force=True)
            service.handle("Przypomnij mi o tym później")
            hidden = service.startup_brief(force=True)
            issue = service.runtime.active.memory.last_issue()
            service.runtime.active.memory.decide(
                issue["fingerprint"],
                "snoozed",
                until=self.now - timedelta(minutes=1),
            )
            due = service.startup_brief(force=True)
        self.assertTrue(first["should_show"])
        self.assertFalse(hidden["should_show"])
        self.assertTrue(due["should_show"])
        self.assertTrue(due["message"].startswith("Przypomnienie:"))

    def test_b169_ignore_suppresses_same_issue_but_not_changed_conflict(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, events=self.events)
            service.startup_brief(force=True)
            service.handle("Pomiń to")
            hidden = service.startup_brief(force=True)
            event = online.calendar.events[1]
            shifted = datetime.fromisoformat(event["start_at"]) + timedelta(minutes=5)
            event["start_at"] = shifted.isoformat()
            event["end_at"] = (shifted + timedelta(hours=1)).isoformat()
            changed = service.startup_brief(force=True)
        self.assertFalse(hidden["should_show"])
        self.assertTrue(changed["should_show"])

    def test_b169_mark_done_is_local_and_does_not_mutate_services(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, events=self.events)
            service.startup_brief(force=True)
            plan = service.plan("Oznacz to jako zrobione")
            response = service.handle("Oznacz to jako zrobione")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("Nie zmieniłem kalendarza ani poczty", response)
        self.assertEqual(online.calendar.updated, [])
        self.assertEqual(online.gmail.drafts, [])

    def test_b170_duplicate_execution_guard_blocks_second_move(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, events=self.events)
            command = "Przenieś drugie spotkanie z konfliktu na 20"
            first = service.handle(command)
            second = service.handle(command)
        self.assertIn("Przeniosłem", first)
        self.assertIn("już wykonane", second)
        self.assertEqual(len(online.calendar.updated), 1)

    def test_b170_status_and_source_bounds(self):
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory)
            status = service.status()
        for stage in ("B166", "B167", "B168", "B169", "B170"):
            self.assertIn(stage, status["stages"])
        active = status["active_resolution"]
        self.assertEqual(active["status"], "ACTIVE_RESOLUTION_READY")
        self.assertTrue(active["writes_require_confirmation"])
        self.assertFalse(active["automatic_calendar_changes"])
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/service.py": 320,
            "app/natural_actions/runtime.py": 140,
            "app/natural_actions/advanced_understanding.py": 220,
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/active_resolution_analysis.py": 240,
            "app/natural_actions/active_resolution_memory.py": 140,
            "app/natural_actions/active_understanding.py": 150,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

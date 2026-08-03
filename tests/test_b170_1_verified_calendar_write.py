from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class FalseSuccessCalendar:
    def __init__(self, events):
        self.events = [dict(item) for item in events]
        self.updated = []
        self.persist = False

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
        self.updated.append(event_id)
        end = start_at + timedelta(minutes=duration_minutes)
        if self.persist:
            for item in self.events:
                if item["id"] == event_id:
                    item["start_at"] = start_at.isoformat()
                    item["end_at"] = end.isoformat()
        return {
            "status": "GOOGLE_CALENDAR_EVENT_UPDATED",
            "event_id": event_id,
            "title": title,
            "start_at": start_at.isoformat(),
            "end_at": end.isoformat(),
        }


class B1701VerifiedCalendarWriteTests(unittest.TestCase):
    def events(self):
        now = datetime.now().astimezone().replace(microsecond=0)
        start = (now + timedelta(days=1)).replace(hour=18, minute=0)
        return [
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

    def test_false_google_success_is_not_reported_as_completed(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=[])
            calendar = FalseSuccessCalendar(self.events())
            online.calendar = calendar
            service = NaturalActionService(directory, online=online)
            service.handle("Co mam zrobić z tym konfliktem?")
            with self.assertRaisesRegex(ValueError, "nie potwierdził"):
                service.handle("Zrób to")
            self.assertFalse(service.context.execution_result(
                service.runtime.fingerprint(service._prepare("Zrób to"))
            ))

    def test_retry_succeeds_only_after_fresh_calendar_read_matches(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=[])
            calendar = FalseSuccessCalendar(self.events())
            online.calendar = calendar
            service = NaturalActionService(directory, online=online)
            service.handle("Co mam zrobić z tym konfliktem?")
            with self.assertRaises(ValueError):
                service.handle("Zrób to")
            calendar.persist = True
            response = service.handle("Zrób to")
            issue = service.runtime.active.analyzer.conflict_issue()
        self.assertIn("Sprawdziłem nowy termin w Google Calendar", response)
        self.assertEqual(issue, {})
        self.assertEqual(calendar.updated, ["event-b", "event-b"])

    def test_source_limits_remain_safe(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/active_resolution.py": 360,
            "app/online_assistant/google_workspace_calendar_writes.py": 120,
        }
        for relative, limit in limits.items():
            lines = (root / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, relative)


if __name__ == "__main__":
    unittest.main()

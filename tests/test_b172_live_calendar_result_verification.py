from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.gui.confirmation_revision_runtime import handle_owner_confirmation
from app.jarvis_experience.smart_task_loop import SmartTaskLoop
from app.natural_actions.calendar_result_verifier import (
    CalendarResultVerificationError,
    CalendarLiveResultVerifier,
)
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class SnapshotCalendar:
    def __init__(self, events, mode="unchanged"):
        self.events = [dict(item) for item in events]
        self.mode = mode
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
        self.updated.append(event_id)
        expected_end = start_at + timedelta(minutes=duration_minutes)
        for event in self.events:
            if event["id"] != event_id or self.mode == "unchanged":
                continue
            event["title"] = "Inny tytuł" if self.mode == "wrong_title" else title
            event["start_at"] = start_at.isoformat()
            actual_end = (
                expected_end + timedelta(minutes=15)
                if self.mode == "wrong_end" else expected_end
            )
            event["end_at"] = actual_end.isoformat()
        returned_id = "other-event" if self.mode == "wrong_response_id" else event_id
        return {
            "status": "GOOGLE_CALENDAR_EVENT_UPDATED",
            "event_id": returned_id,
            "title": title,
            "start_at": start_at.isoformat(),
            "end_at": expected_end.isoformat(),
        }


class _Brain:
    def execute(self, _thought):
        raise CalendarResultVerificationError(
            CalendarLiveResultVerifier.MESSAGE
        )


class _Console:
    def __init__(self):
        self.lines = []
        self.states = []

    def append(self, text):
        self.lines.append(text)

    def set_state(self, label, style):
        self.states.append((label, style))


class _OwnerWindow:
    def __init__(self):
        self.pending_thought = {"handler": "personal_assistant"}
        self.brain = _Brain()
        self.console_page = _Console()
        self.spoken = []

    def say_safe(self, text):
        self.spoken.append(text)


class B172LiveCalendarResultVerificationTests(unittest.TestCase):
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

    def service(self, directory, mode):
        online = FakeOnline(directory, events=[])
        online.calendar = SnapshotCalendar(self.events(), mode=mode)
        return NaturalActionService(directory, online=online), online

    def execute_suggestion(self, service):
        service.handle("Co mam zrobić z tym konfliktem?")
        return service.handle("Zrób to")

    def test_false_write_response_is_rejected_by_independent_live_read(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, "unchanged")
            with self.assertRaisesRegex(
                CalendarResultVerificationError, "Nie zgłaszam sukcesu"
            ):
                self.execute_suggestion(service)
        self.assertEqual(online.calendar.updated, ["event-b"])

    def test_live_end_must_match_preserved_duration(self):
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory, "wrong_end")
            with self.assertRaises(CalendarResultVerificationError):
                self.execute_suggestion(service)

    def test_live_title_must_match_expected_event(self):
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory, "wrong_title")
            with self.assertRaises(CalendarResultVerificationError):
                self.execute_suggestion(service)

    def test_write_response_event_id_must_match(self):
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory, "wrong_response_id")
            with self.assertRaises(CalendarResultVerificationError):
                self.execute_suggestion(service)

    def test_success_uses_full_live_snapshot(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, "exact")
            response = self.execute_suggestion(service)
        event = online.calendar.events[1]
        self.assertIn("Sprawdziłem nowy termin w Google Calendar", response)
        self.assertEqual(event["title"], "Spotkanie B")
        self.assertEqual(
            datetime.fromisoformat(event["end_at"])
            - datetime.fromisoformat(event["start_at"]),
            timedelta(hours=1),
        )

    def test_client_and_owner_receive_safe_verification_message(self):
        loop = SmartTaskLoop(_Brain(), lambda _c, _r: {"allowed": True}, lambda _t: True)
        outcome = loop.execute({"handler": "personal_assistant"})
        self.assertEqual(outcome.status, "CALENDAR_UNVERIFIED")
        self.assertEqual(outcome.message, CalendarLiveResultVerifier.MESSAGE)
        self.assertNotIn("C:/JarvisAI", outcome.message)

        window = _OwnerWindow()
        handle_owner_confirmation(window, "TAK")
        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.spoken, [CalendarLiveResultVerifier.MESSAGE])
        self.assertEqual(
            window.console_page.states[-1],
            ("ZMIANA NIEPOTWIERDZONA", "danger"),
        )

    def test_b172_status_and_source_bounds(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=self.events()),
            )
            status = service.status()
        self.assertEqual(
            status["stages"]["B172"],
            "LIVE_CALENDAR_RESULT_VERIFICATION_READY",
        )
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/calendar_result_verifier.py": 120,
            "app/natural_actions/service.py": 320,
            "app/jarvis_experience/smart_task_loop.py": 130,
            "app/gui/confirmation_revision_runtime.py": 80,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

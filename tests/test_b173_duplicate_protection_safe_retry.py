from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.jarvis_experience.smart_task_loop import SmartTaskLoop
from app.natural_actions.calendar_safe_retry import CalendarSafeRetryError
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class RetryCalendar:
    def __init__(self, events, mode="exact"):
        self.events = [dict(item) for item in events]
        self.mode = mode
        self.updated = []
        self.reads = 0
        self.read_error = False

    def find_events(self, _query, *, start_at, end_at, max_results=20):
        self.reads += 1
        if self.read_error:
            raise RuntimeError("temporary read failure")
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
        call = len(self.updated)
        if self.mode == "fail_once" and call == 1:
            raise RuntimeError("temporary write failure")
        if self.mode == "always_fail":
            raise RuntimeError("write unavailable")
        self._apply(event_id, title, start_at, duration_minutes)
        if self.mode == "lost_after_write" and call == 1:
            raise RuntimeError("response lost")
        if self.mode == "unknown_after_write" and call == 1:
            self.read_error = True
            raise RuntimeError("response and read lost")
        return {
            "status": "GOOGLE_CALENDAR_EVENT_UPDATED",
            "event_id": event_id,
            "title": title,
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(minutes=duration_minutes)).isoformat(),
        }

    def _apply(self, event_id, title, start_at, duration_minutes):
        for event in self.events:
            if event["id"] == event_id:
                event["title"] = title
                event["start_at"] = start_at.isoformat()
                event["end_at"] = (
                    start_at + timedelta(minutes=duration_minutes)
                ).isoformat()


class _RetryBrain:
    def execute(self, _thought):
        raise CalendarSafeRetryError(CalendarSafeRetryError.MESSAGE)


class B173DuplicateProtectionSafeRetryTests(unittest.TestCase):
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

    def staged(self, directory, mode="exact"):
        online = FakeOnline(directory, events=[])
        online.calendar = RetryCalendar(self.events(), mode=mode)
        service = NaturalActionService(directory, online=online)
        service.handle("Co mam zrobić z tym konfliktem?")
        thought = service.plan("Zrób to.")
        assistant = type("Assistant", (), {"natural_actions": service})()
        return service, online, thought, assistant

    def test_lost_response_is_verified_without_second_write(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(
                directory, "lost_after_write"
            )
            response = PlannedNaturalActionExecutor.execute(assistant, thought)
        self.assertIn("Sprawdziłem nowy termin", response)
        self.assertEqual(online.calendar.updated, ["event-b"])

    def test_safe_retry_runs_once_only_when_live_write_is_absent(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(
                directory, "fail_once"
            )
            response = PlannedNaturalActionExecutor.execute(assistant, thought)
        self.assertIn("Przeniosłem", response)
        self.assertEqual(online.calendar.updated, ["event-b", "event-b"])

    def test_safe_retry_is_bounded_to_one_repeat(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(
                directory, "always_fail"
            )
            with self.assertRaisesRegex(
                CalendarSafeRetryError, "kolejnej próby"
            ):
                PlannedNaturalActionExecutor.execute(assistant, thought)
        self.assertEqual(online.calendar.updated, ["event-b", "event-b"])

    def test_unknown_live_state_never_triggers_blind_retry(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(
                directory, "unknown_after_write"
            )
            with self.assertRaises(CalendarSafeRetryError):
                PlannedNaturalActionExecutor.execute(assistant, thought)
        self.assertEqual(online.calendar.updated, ["event-b"])

    def test_completed_operation_receipt_blocks_late_duplicate(self):
        with TemporaryDirectory() as directory:
            service, online, thought, assistant = self.staged(directory)
            first = PlannedNaturalActionExecutor.execute(assistant, thought)
            data = service.context.load()
            data["executions"] = []
            service.context.store.save(data)
            second = PlannedNaturalActionExecutor.execute(assistant, thought)
            receipts = service.runtime.active.move_executor.ledger._items()
        self.assertIn("Przeniosłem", first)
        self.assertIn("już wykonana", second)
        self.assertEqual(online.calendar.updated, ["event-b"])
        self.assertEqual(receipts[-1]["status"], "COMPLETED")
        self.assertEqual(len(receipts[-1]["operation_key"]), 32)

    def test_immediate_repeated_confirmation_uses_existing_once_guard(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(directory)
            PlannedNaturalActionExecutor.execute(assistant, thought)
            response = PlannedNaturalActionExecutor.execute(assistant, thought)
        self.assertEqual(
            response,
            "Ta zmiana została już wykonana. Nie wykonałem jej ponownie.",
        )
        self.assertEqual(online.calendar.updated, ["event-b"])

    def test_client_receives_safe_nontechnical_retry_message(self):
        loop = SmartTaskLoop(
            _RetryBrain(), lambda _c, _r: {"allowed": True}, lambda _t: True
        )
        outcome = loop.execute({"handler": "personal_assistant"})
        self.assertEqual(outcome.status, "CALENDAR_UNVERIFIED")
        self.assertEqual(outcome.message, CalendarSafeRetryError.MESSAGE)
        self.assertNotIn("RuntimeError", outcome.message)
        self.assertNotIn("C:/JarvisAI", outcome.message)

    def test_default_calendar_lookup_window_starts_at_local_midnight(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=self.events()),
            )
            start, end = service.advanced._window(None)
        now = datetime.now().astimezone()
        self.assertEqual(start.date(), now.date())
        self.assertEqual(start.timetz().replace(tzinfo=None), time.min)
        self.assertGreater(end, start)

    def test_b173_status_and_source_bounds(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=self.events()),
            )
            status = service.status()
        self.assertEqual(
            status["stages"]["B173"],
            "DUPLICATE_PROTECTION_SAFE_RETRY_READY",
        )
        self.assertTrue(status["active_resolution"]["duplicate_protection"])
        self.assertEqual(status["active_resolution"]["safe_retry_limit"], 1)
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/calendar_result_verifier.py": 120,
            "app/natural_actions/calendar_safe_retry.py": 300,
            "app/natural_actions/advanced_actions.py": 200,
            "app/natural_actions/service.py": 320,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

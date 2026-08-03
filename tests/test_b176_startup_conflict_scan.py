from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.service import NaturalActionService
from app.natural_actions.startup_conflict_scan import StartupConflictScanService


class FakeProvider:
    pass


class FakeCalendar:
    def __init__(self, events_by_day=None):
        self.events_by_day = dict(events_by_day or {})

    def find_events(self, _query, *, start_at, end_at, max_results=20):
        return list(self.events_by_day.get(start_at.date().isoformat(), []))


class FakeGmail:
    def priority(self, _limit=5):
        return []


class FakeReminders:
    def status(self):
        return {"due_count": 0, "pending_count": 0}


class FakeOnline:
    def __init__(self, root):
        self.project_root = Path(root)
        self.provider = FakeProvider()
        self.calendar = FakeCalendar()
        self.gmail = FakeGmail()
        self.reminders = FakeReminders()


class B176StartupConflictScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now().astimezone().replace(microsecond=0)

    def _snapshot(self, offset: int, events=None):
        return {
            "day_offset": offset,
            "now": self.now,
            "events": list(events or []),
            "mail": [],
            "reminders": {"due_count": 0, "pending_count": 0},
            "completed": [],
        }

    def _conflict(self, *, tomorrow=False):
        start = self.now + timedelta(days=1 if tomorrow else 0, hours=2)
        return [
            {
                "id": "a",
                "title": "Spotkanie A",
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(hours=1)).isoformat(),
            },
            {
                "id": "b",
                "title": "Spotkanie B",
                "start_at": (start + timedelta(minutes=30)).isoformat(),
                "end_at": (start + timedelta(hours=1, minutes=30)).isoformat(),
            },
        ]

    def test_b176_detects_today_conflict_on_startup(self):
        provider = lambda offset: self._snapshot(
            offset, self._conflict() if offset == 0 else []
        )
        result = StartupConflictScanService(provider).scan()
        self.assertTrue(result["should_show"])
        self.assertEqual(result["conflict_count"], 1)
        self.assertIn("Spotkanie A", result["message"])
        self.assertIn("Co mam zrobić z tym konfliktem", result["message"])

    def test_b176_detects_tomorrow_conflict_on_startup(self):
        provider = lambda offset: self._snapshot(
            offset, self._conflict(tomorrow=True) if offset == 1 else []
        )
        result = StartupConflictScanService(provider).scan()
        self.assertTrue(result["should_show"])
        self.assertEqual(result["level"], "critical")

    def test_b176_quiet_calendar_does_not_show_alert(self):
        result = StartupConflictScanService(
            lambda offset: self._snapshot(offset)
        ).scan()
        self.assertFalse(result["should_show"])
        self.assertEqual(result["conflict_count"], 0)
        self.assertTrue(result["scan_completed"])

    def test_b176_duplicate_event_from_two_days_is_not_conflict(self):
        event = self._conflict()[0]
        result = StartupConflictScanService(
            lambda offset: self._snapshot(offset, [event])
        ).scan()
        self.assertFalse(result["should_show"])
        self.assertEqual(result["conflict_count"], 0)

    def test_b176_scan_is_silent_and_never_writes(self):
        result = StartupConflictScanService(
            lambda offset: self._snapshot(
                offset, self._conflict() if offset == 0 else []
            )
        ).scan()
        self.assertFalse(result["speak"])
        self.assertFalse(result["automatic_writes"])

    def test_b176_service_exposes_stage_and_status(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory, online=FakeOnline(directory)
            )
            status = service.status()
        self.assertIn("B176", status["stages"])
        self.assertEqual(
            status["startup_conflicts"]["status"],
            "STARTUP_CONFLICT_SCAN_READY",
        )
        self.assertFalse(status["startup_conflicts"]["automatic_writes"])

    def test_b176_client_runs_scan_before_daily_brief_once(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/client_online_mixin.py").read_text(
            encoding="utf-8"
        )
        window = (root / "app/gui/client_experience_window.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _show_startup_conflict_scan", source)
        self.assertIn("ClientStartupConflictRuntime", source)
        self.assertIn("self._startup_conflict_runtime().arm()", source)
        self.assertIn(
            "QTimer.singleShot(0, self._schedule_proactive_brief)",
            window,
        )

    def test_b176_source_limits(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/startup_conflict_scan.py": 100,
            "app/gui/client_online_mixin.py": 150,
            "app/gui/client_startup_conflict_runtime.py": 100,
            "app/natural_actions/runtime.py": 180,
        }
        for relative, limit in limits.items():
            lines = (root / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, relative)


if __name__ == "__main__":
    unittest.main()

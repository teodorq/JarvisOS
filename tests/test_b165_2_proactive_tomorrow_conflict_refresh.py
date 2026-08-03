from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.proactive_day import ProactiveDayService


class B1652TomorrowConflictRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now().astimezone().replace(microsecond=0)

    def _snapshot(self, offset: int, events=None, due: int = 0):
        return {
            "day_offset": offset,
            "now": self.now,
            "events": list(events or []),
            "mail": [],
            "reminders": {"due_count": due, "pending_count": due},
            "completed": [],
        }

    def _tomorrow_conflict(self):
        start = self.now + timedelta(days=1, hours=2)
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

    def test_tomorrow_conflict_is_included_in_startup_brief(self):
        conflict = self._tomorrow_conflict()
        provider = lambda offset: self._snapshot(
            offset, conflict if offset == 1 else []
        )
        with TemporaryDirectory() as directory:
            result = ProactiveDayService(
                directory, provider, now_provider=lambda: self.now
            ).startup_brief()
        self.assertEqual(result["conflict_count"], 1)
        self.assertIn("Spotkanie A", result["message"])
        self.assertIn("Spotkanie B", result["message"])

    def test_new_conflict_breaks_previous_critical_suppression(self):
        state = {"conflict": False}
        conflict = self._tomorrow_conflict()
        def provider(offset):
            events = conflict if offset == 1 and state["conflict"] else []
            return self._snapshot(offset, events, due=1)
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory, provider, now_provider=lambda: self.now
            )
            first = service.startup_brief()
            state["conflict"] = True
            second = service.startup_brief()
        self.assertTrue(first["should_show"])
        self.assertTrue(second["should_show"])
        self.assertEqual(second["conflict_count"], 1)

    def test_duplicate_event_from_both_snapshots_is_not_a_conflict(self):
        event = self._tomorrow_conflict()[0]
        provider = lambda offset: self._snapshot(offset, [event])
        with TemporaryDirectory() as directory:
            result = ProactiveDayService(
                directory, provider, now_provider=lambda: self.now
            ).startup_brief()
        self.assertEqual(result["conflict_count"], 0)

    def test_client_window_refreshes_after_startup_scan_on_every_show(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/client_online_mixin.py").read_text(
            encoding="utf-8"
        )
        runtime = (
            root / "app/gui/client_startup_conflict_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def showEvent", source)
        self.assertIn("self._startup_conflict_runtime().arm()", source)
        self.assertIn(
            "QTimer.singleShot(150, self.window._show_proactive_brief)",
            runtime,
        )

    def test_source_limits(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/proactive_day.py": 300,
            "app/gui/client_online_mixin.py": 140,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)


if __name__ == "__main__":
    unittest.main()

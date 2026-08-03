from __future__ import annotations

from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.proactive_day import ProactiveDayService


class B1654ConflictFingerprintRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now().astimezone().replace(microsecond=0)
        self.offset_minutes = 30

    def _events(self):
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
                "start_at": (start + timedelta(minutes=self.offset_minutes)).isoformat(),
                "end_at": (start + timedelta(minutes=self.offset_minutes + 60)).isoformat(),
            },
        ]

    def _snapshot(self, offset: int):
        return {
            "day_offset": offset,
            "now": self.now,
            "events": self._events() if offset == 1 else [],
            "mail": [],
            "reminders": {"due_count": 0, "pending_count": 0},
            "completed": [],
        }

    def test_changed_overlap_time_with_same_conflict_count_is_shown_again(self):
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory, self._snapshot, now_provider=lambda: self.now
            )
            first = service.startup_brief()
            self.offset_minutes = 45
            second = service.startup_brief()
        self.assertTrue(first["should_show"])
        self.assertTrue(second["should_show"])
        self.assertEqual(first["conflict_count"], 1)
        self.assertEqual(second["conflict_count"], 1)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])
        self.assertNotEqual(first["message"], second["message"])
        self.assertIn("Spotkanie A", second["message"])
        self.assertIn("Spotkanie B", second["message"])

    def test_identical_critical_brief_is_still_suppressed(self):
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory, self._snapshot, now_provider=lambda: self.now
            )
            first = service.startup_brief()
            second = service.startup_brief()
        self.assertTrue(first["should_show"])
        self.assertFalse(second["should_show"])
        self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_source_limit(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/natural_actions/proactive_day.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(source.splitlines()), 300)


if __name__ == "__main__":
    unittest.main()

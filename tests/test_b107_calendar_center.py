from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
import unittest

from app.productivity.calendar_center import LocalCalendarCenter


class B107CalendarCenterTests(unittest.TestCase):
    def test_detects_overlapping_events(self) -> None:
        with TemporaryDirectory() as temporary:
            service = LocalCalendarCenter(temporary)
            start = datetime.now(timezone.utc) + timedelta(hours=2)
            service.add_event("Pierwsze", start, duration_minutes=60)
            service.add_event("Drugie", start + timedelta(minutes=30), duration_minutes=45)
            self.assertEqual(len(service.conflicts()), 1)
            self.assertEqual(service.status()["conflict_count"], 1)

    def test_non_overlapping_events_do_not_conflict(self) -> None:
        with TemporaryDirectory() as temporary:
            service = LocalCalendarCenter(temporary)
            start = datetime.now(timezone.utc) + timedelta(hours=2)
            service.add_event("Pierwsze", start, duration_minutes=30)
            service.add_event("Drugie", start + timedelta(minutes=30), duration_minutes=30)
            self.assertEqual(service.conflicts(), [])

    def test_demo_is_idempotent_for_same_day(self) -> None:
        with TemporaryDirectory() as temporary:
            service = LocalCalendarCenter(temporary)
            first = service.add_demo()
            second = service.add_demo()
            self.assertEqual(first["event_id"], second["event_id"])
            self.assertEqual(service.status()["event_count"], 1)


if __name__ == "__main__":
    unittest.main()

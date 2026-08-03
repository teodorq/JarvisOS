from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
import unittest

from app.productivity.reminder_center import ReminderCenterV2


class B109ReminderCenterTests(unittest.TestCase):
    def test_one_time_reminder_completes(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ReminderCenterV2(temporary)
            service.add("Test", minutes=0)
            self.assertEqual(service.status()["due_count"], 1)
            completed = service.complete()
            self.assertEqual(completed["status"], "COMPLETED")
            self.assertEqual(service.status()["completed_count"], 1)

    def test_daily_reminder_moves_forward(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ReminderCenterV2(temporary)
            due = datetime.now(timezone.utc) - timedelta(minutes=1)
            reminder = service.add("Codziennie", due_at=due, recurrence="DAILY")
            completed = service.complete()
            self.assertEqual(completed["status"], "PENDING")
            self.assertGreater(completed["due_at"], reminder["due_at"])
            self.assertEqual(completed["completion_count"], 1)

    def test_empty_text_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                ReminderCenterV2(temporary).add(" ")


if __name__ == "__main__":
    unittest.main()

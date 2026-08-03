from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.service import NaturalActionService
from app.natural_actions.startup_conflict_notification import (
    StartupConflictNotificationPolicy,
)


class _Provider:
    pass


class _Calendar:
    def find_events(self, _query, *, start_at, end_at, max_results=20):
        return []


class _Gmail:
    def priority(self, _limit=5):
        return []


class _Reminders:
    def status(self):
        return {"due_count": 0, "pending_count": 0}


class _Online:
    def __init__(self, root):
        self.project_root = Path(root)
        self.provider = _Provider()
        self.calendar = _Calendar()
        self.gmail = _Gmail()
        self.reminders = _Reminders()


class B177NewChangedConflictNotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime.now().astimezone().replace(microsecond=0)

    def events(self, shift=0):
        start = self.start + timedelta(minutes=shift)
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

    def result(self, events, *, should_show=True, reactivated=False):
        fingerprint = StartupConflictNotificationPolicy.conflict_fingerprint(events)
        return {
            "should_show": should_show,
            "message": "Wykryłem konflikt.",
            "scan_completed": True,
            "conflict_count": 1 if fingerprint else 0,
            "fingerprint": fingerprint,
            "reactivated_after_undo": reactivated,
            "automatic_writes": False,
        }

    def test_first_conflict_is_shown_and_same_conflict_is_suppressed(self):
        with TemporaryDirectory() as directory:
            first = StartupConflictNotificationPolicy(directory)
            self.assertTrue(first.filter(self.result(self.events()))["should_show"])
            second = StartupConflictNotificationPolicy(directory)
            repeated = second.filter(self.result(self.events()))
            self.assertFalse(repeated["should_show"])
            self.assertTrue(repeated["duplicate_suppressed"])
            self.assertEqual(repeated["notification_reason"], "unchanged")

    def test_changed_conflict_gets_new_fingerprint_and_is_shown(self):
        with TemporaryDirectory() as directory:
            policy = StartupConflictNotificationPolicy(directory)
            first = self.result(self.events())
            changed = self.result(self.events(shift=15))
            policy.filter(first)
            self.assertNotEqual(first["fingerprint"], changed["fingerprint"])
            output = policy.filter(changed)
            self.assertTrue(output["should_show"])
            self.assertEqual(output["notification_reason"], "new")

    def test_quiet_scan_rearms_the_same_conflict(self):
        with TemporaryDirectory() as directory:
            policy = StartupConflictNotificationPolicy(directory)
            policy.filter(self.result(self.events()))
            policy.filter({
                "should_show": False,
                "scan_completed": True,
                "conflict_count": 0,
                "fingerprint": "",
            })
            output = policy.filter(self.result(self.events()))
            self.assertTrue(output["should_show"])

    def test_verified_undo_can_redisplay_same_conflict(self):
        with TemporaryDirectory() as directory:
            policy = StartupConflictNotificationPolicy(directory)
            policy.filter(self.result(self.events()))
            output = policy.filter(
                self.result(self.events(), reactivated=True)
            )
            self.assertTrue(output["should_show"])
            self.assertEqual(output["notification_reason"], "changed")

    def test_active_decision_suppression_does_not_clear_fingerprint(self):
        with TemporaryDirectory() as directory:
            policy = StartupConflictNotificationPolicy(directory)
            policy.filter(self.result(self.events()))
            hidden = policy.filter(self.result(self.events(), should_show=False))
            self.assertEqual(hidden["notification_reason"], "suppressed_by_decision")
            repeated = policy.filter(self.result(self.events()))
            self.assertFalse(repeated["should_show"])

    def test_fingerprint_uses_only_overlapping_event_pairs(self):
        base = self.events()
        extra = {
            "id": "c",
            "title": "Obiad",
            "start_at": (self.start + timedelta(hours=5)).isoformat(),
            "end_at": (self.start + timedelta(hours=6)).isoformat(),
        }
        self.assertEqual(
            StartupConflictNotificationPolicy.conflict_fingerprint(base),
            StartupConflictNotificationPolicy.conflict_fingerprint(base + [extra]),
        )

    def test_service_exposes_b177_and_read_only_status(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(directory, online=_Online(directory))
            status = service.status()
        self.assertIn("B177", status["stages"])
        notifications = status["startup_notifications"]
        self.assertEqual(
            notifications["status"],
            "NEW_CHANGED_CONFLICT_NOTIFICATION_READY",
        )
        self.assertFalse(notifications["automatic_writes"])

    def test_runtime_and_reactivation_are_wired(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "app/natural_actions/service.py").read_text(
            encoding="utf-8"
        )
        runtime = (root / "app/natural_actions/runtime.py").read_text(
            encoding="utf-8"
        )
        reactivation = (
            root / "app/natural_actions/startup_conflict_reactivation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("startup_notifications.filter(", service)
        self.assertIn("StartupConflictNotificationPolicy", runtime)
        self.assertIn('result["reactivated_after_undo"] = True', reactivation)

    def test_b177_never_writes_calendar_and_source_bounds(self):
        root = Path(__file__).resolve().parents[1]
        relative = "app/natural_actions/startup_conflict_notification.py"
        source = (root / relative).read_text(encoding="utf-8")
        for marker in ("create_event(", "update_event(", "delete_event("):
            self.assertNotIn(marker, source)
        self.assertLess(len(source.splitlines()), 140)


if __name__ == "__main__":
    unittest.main()

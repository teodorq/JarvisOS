from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.active_resolution_analysis import ActiveIssueAnalyzer
from app.natural_actions.active_resolution_memory import ActiveResolutionMemory
from app.natural_actions.conflict_alert_context import ConflictAlertContext
from app.natural_actions.service import NaturalActionService
from app.natural_actions.startup_conflict_notification import (
    StartupConflictNotificationPolicy,
)
from app.natural_actions.startup_conflict_scan import StartupConflictScanService
from tests.test_b166_b170_active_resolution import FakeOnline


class B181ExactAlertConflictContextTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime.now().astimezone().replace(microsecond=0)
        self.start = (now + timedelta(days=1)).replace(hour=18, minute=0)
        self.events = [
            self.event("event-a", "Spotkanie A", self.start, 60),
            self.event("event-b", "Spotkanie B", self.start + timedelta(minutes=30), 60),
        ]

    @staticmethod
    def event(event_id, title, start, duration):
        return {
            "id": event_id,
            "title": title,
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(minutes=duration)).isoformat(),
        }

    def test_context_contains_the_exact_alert_pair(self):
        context = ConflictAlertContext.analyze(self.events)[0]
        pair = ConflictAlertContext.exact_pair(context)

        self.assertEqual(pair["first_id"], "event-a")
        self.assertEqual(pair["second_id"], "event-b")
        self.assertEqual(pair["second_start"], self.events[1]["start_at"])
        self.assertEqual(context["at"], "18:30")
        expected = ActiveIssueAnalyzer.with_fingerprint({
            "type": "conflict",
            "first": dict(context["first"]),
            "second": dict(context["second"]),
            "at": "18:30",
        })
        self.assertEqual(context["fingerprint"], expected["fingerprint"])
        self.assertTrue(context["alert_context"])

    def test_startup_scan_message_and_context_refer_to_the_same_events(self):
        scan = StartupConflictScanService(
            lambda offset: {"events": self.events if offset == 1 else []}
        ).scan()

        context = scan["conflict_context"]
        self.assertTrue(scan["should_show"])
        self.assertEqual(context["first"]["id"], "event-a")
        self.assertEqual(context["second"]["id"], "event-b")
        self.assertIn(context["first"]["title"], scan["message"])
        self.assertIn(context["second"]["title"], scan["message"])
        self.assertIn(context["at"], scan["message"])
        self.assertFalse(scan["automatic_writes"])

    def test_only_a_shown_alert_replaces_the_persisted_context(self):
        with TemporaryDirectory() as directory:
            policy = StartupConflictNotificationPolicy(directory)
            first = ConflictAlertContext.analyze(self.events)[0]
            result = policy.filter({
                "scan_completed": True,
                "should_show": True,
                "conflict_count": 1,
                "fingerprint": "same-alert",
                "conflict_context": first,
            })
            self.assertTrue(result["should_show"])

            replacement = dict(first)
            replacement["second"] = dict(first["second"], id="wrong-event")
            duplicate = policy.filter({
                "scan_completed": True,
                "should_show": True,
                "conflict_count": 1,
                "fingerprint": "same-alert",
                "conflict_context": replacement,
            })
            stored = ActiveResolutionMemory(directory).last_issue()

        self.assertFalse(duplicate["should_show"])
        self.assertEqual(stored["second"]["id"], "event-b")

    def test_follow_up_uses_the_exact_pair_from_the_alert(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=self.events)
            service = NaturalActionService(directory, online=online)
            shown = service.startup_conflict_scan()
            self.assertTrue(shown["should_show"])

            earlier = self.start - timedelta(hours=3)
            online.calendar.events.extend([
                self.event("event-c", "Spotkanie C", earlier, 60),
                self.event("event-d", "Spotkanie D", earlier + timedelta(minutes=15), 60),
            ])
            response = service.handle("Co mam zrobić z tym konfliktem?")

        self.assertIn("Spotkanie B", response)
        self.assertNotIn("Spotkanie D", response)

    def test_exact_alert_context_survives_service_recreation(self):
        with TemporaryDirectory() as directory:
            first = NaturalActionService(
                directory, online=FakeOnline(directory, events=self.events)
            )
            first.startup_conflict_scan()

            earlier = self.start - timedelta(hours=3)
            events = self.events + [
                self.event("event-c", "Spotkanie C", earlier, 60),
                self.event("event-d", "Spotkanie D", earlier + timedelta(minutes=15), 60),
            ]
            second = NaturalActionService(
                directory, online=FakeOnline(directory, events=events)
            )
            response = second.handle("Co mam zrobić z tym konfliktem?")

        self.assertIn("Spotkanie B", response)
        self.assertNotIn("Spotkanie D", response)

    def test_stage_and_config_match_the_read_only_contract(self):
        with TemporaryDirectory() as directory:
            status = NaturalActionService(
                directory, online=FakeOnline(directory, events=[])
            ).status()
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "config/b181_exact_alert_conflict_context.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            status["stages"]["B181"],
            "EXACT_ALERT_CONFLICT_CONTEXT_READY",
        )
        self.assertTrue(config["contract"]["follow_up_uses_alert_context"])
        self.assertFalse(config["contract"]["automatic_calendar_writes"])
        self.assertTrue(config["contract"]["confirmation_required_for_writes"])

    def test_b181_is_bounded_read_only_and_has_no_fixed_project_path(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/conflict_alert_context.py": 100,
            "app/natural_actions/startup_conflict_scan.py": 100,
            "app/natural_actions/startup_conflict_notification.py": 140,
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/service.py": 320,
            "tests/test_b181_exact_alert_conflict_context.py": 180,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:" + "/JarvisAI", source.replace("\\", "/"))
        b181 = (root / "app/natural_actions/conflict_alert_context.py").read_text(
            encoding="utf-8"
        )
        for marker in ("create_event(", "update_event(", "delete_event(", "move_event("):
            self.assertNotIn(marker, b181)


if __name__ == "__main__":
    unittest.main()

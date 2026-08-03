from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class B182ExactSafeConflictProposalTests(unittest.TestCase):
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

    def service(self, directory, events=None):
        online = FakeOnline(directory, events=events or self.events)
        return NaturalActionService(directory, online=online), online

    def test_proposal_rereads_live_calendar_and_chooses_free_target(self):
        busy = self.event("event-c", "Spotkanie C", self.start + timedelta(hours=1), 60)
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, self.events + [busy])
            service.startup_conflict_scan()
            response = service.handle("Co mam zrobić z tym konfliktem?")
            suggestion = service.runtime.active.memory.last_suggestion()

        self.assertIn("Spotkanie B", response)
        self.assertIn("20:00", response)
        self.assertEqual(datetime.fromisoformat(suggestion["new_when"]).hour, 20)
        self.assertEqual(online.calendar.updated, [])

    def test_proposal_uses_exact_shown_pair_not_an_earlier_new_conflict(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory)
            shown = service.startup_conflict_scan()
            self.assertTrue(shown["should_show"])
            earlier = self.start - timedelta(hours=4)
            online.calendar.events.extend([
                self.event("event-c", "Spotkanie C", earlier, 60),
                self.event("event-d", "Spotkanie D", earlier + timedelta(minutes=15), 60),
            ])
            response = service.handle("Co mam zrobić z tym konfliktem?")
            suggestion = service.runtime.active.memory.last_suggestion()

        self.assertIn("Spotkanie B", response)
        self.assertNotIn("Spotkanie D", response)
        self.assertEqual(suggestion["event_id"], "event-b")

    def test_changed_exact_pair_is_rejected_before_a_proposal_is_saved(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory)
            service.startup_conflict_scan()
            shifted = self.start + timedelta(minutes=45)
            online.calendar.events[1]["start_at"] = shifted.isoformat()
            online.calendar.events[1]["end_at"] = (
                shifted + timedelta(hours=1)
            ).isoformat()

            with self.assertRaisesRegex(ValueError, "Konflikt zmienił się"):
                service.handle("Co mam zrobić z tym konfliktem?")

            suggestion = service.runtime.active.memory.last_suggestion()

        self.assertEqual(suggestion, {})
        self.assertEqual(online.calendar.updated, [])

    def test_proposal_preserves_the_live_event_duration(self):
        events = [
            self.event("event-a", "Spotkanie A", self.start, 60),
            self.event("event-b", "Spotkanie B", self.start + timedelta(minutes=30), 75),
        ]
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory, events)
            service.startup_conflict_scan()
            service.handle("Co mam zrobić z tym konfliktem?")
            suggestion = service.runtime.active.memory.last_suggestion()

        self.assertEqual(suggestion["duration_minutes"], 75)
        self.assertTrue(suggestion["proposal_read_only"])
        self.assertTrue(suggestion["proposal_live_verified"])

    def test_advice_is_read_only_and_apply_still_requires_confirmation(self):
        with TemporaryDirectory() as directory:
            service, online = self.service(directory)
            service.startup_conflict_scan()
            advice = service.plan("Co mam zrobić z tym konfliktem?")
            service.handle("Co mam zrobić z tym konfliktem?")
            apply_plan = service.plan("Zrób to.")

        self.assertTrue(advice["read_only"])
        self.assertFalse(advice["requires_confirmation"])
        self.assertTrue(apply_plan["requires_confirmation"])
        self.assertEqual(online.calendar.updated, [])

    def test_suggested_target_has_no_live_overlap(self):
        busy = self.event("event-c", "Spotkanie C", self.start + timedelta(hours=1), 45)
        with TemporaryDirectory() as directory:
            service, online = self.service(directory, self.events + [busy])
            service.startup_conflict_scan()
            service.handle("Co mam zrobić z tym konfliktem?")
            suggestion = service.runtime.active.memory.last_suggestion()

        target = datetime.fromisoformat(suggestion["new_when"])
        target_end = target + timedelta(minutes=suggestion["duration_minutes"])
        for event in online.calendar.events:
            if event["id"] == suggestion["event_id"]:
                continue
            start = datetime.fromisoformat(event["start_at"])
            end = datetime.fromisoformat(event["end_at"])
            self.assertFalse(target < end and target_end > start)

    def test_stage_config_status_and_source_bounds(self):
        with TemporaryDirectory() as directory:
            service, _online = self.service(directory)
            status = service.status()
            proposal = service.runtime.active.exact_proposal.status()

        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "config/b182_exact_safe_conflict_proposal.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            status["stages"]["B182"], "EXACT_SAFE_CONFLICT_PROPOSAL_READY"
        )
        self.assertEqual(
            proposal["status"], "EXACT_SAFE_CONFLICT_PROPOSAL_READY"
        )
        self.assertFalse(config["contract"]["automatic_calendar_writes"])
        self.assertTrue(config["contract"]["execution_requires_confirmation"])
        limits = {
            "app/natural_actions/exact_conflict_proposal.py": 130,
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/service.py": 320,
            "tests/test_b182_exact_safe_conflict_proposal.py": 190,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:" + "/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

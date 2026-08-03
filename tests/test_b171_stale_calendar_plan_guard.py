from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class B171StaleCalendarPlanGuardTests(unittest.TestCase):
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

    def staged(self, directory):
        online = FakeOnline(directory, events=self.events())
        service = NaturalActionService(directory, online=online)
        service.handle("Co mam zrobić z tym konfliktem?")
        thought = service.plan("Zrób to.")
        assistant = type("Assistant", (), {"natural_actions": service})()
        return service, online, thought, assistant

    def test_external_event_move_blocks_confirmed_stale_plan(self):
        with TemporaryDirectory() as directory:
            service, online, thought, assistant = self.staged(directory)
            event = online.calendar.events[1]
            shifted = datetime.fromisoformat(event["start_at"]) + timedelta(minutes=15)
            event["start_at"] = shifted.isoformat()
            event["end_at"] = (shifted + timedelta(hours=1)).isoformat()

            with self.assertRaisesRegex(ValueError, "nieaktualny"):
                PlannedNaturalActionExecutor.execute(assistant, thought)

            self.assertEqual(online.calendar.updated, [])
            self.assertEqual(
                service.runtime.active.memory.last_suggestion(),
                {},
            )

    def test_deleted_event_blocks_write(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(directory)
            online.calendar.events = [online.calendar.events[0]]

            with self.assertRaisesRegex(ValueError, "Nie wykonałem"):
                PlannedNaturalActionExecutor.execute(assistant, thought)

            self.assertEqual(online.calendar.updated, [])

    def test_new_target_conflict_blocks_write(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(directory)
            target = datetime.fromisoformat(
                thought["natural_slots"]["new_when"]
            )
            online.calendar.events.append({
                "id": "event-c",
                "title": "Nowe spotkanie",
                "start_at": target.isoformat(),
                "end_at": (target + timedelta(minutes=30)).isoformat(),
            })

            with self.assertRaisesRegex(ValueError, "ponowne sprawdzenie"):
                PlannedNaturalActionExecutor.execute(assistant, thought)

            self.assertEqual(online.calendar.updated, [])

    def test_unchanged_confirmed_plan_executes_once(self):
        with TemporaryDirectory() as directory:
            _service, online, thought, assistant = self.staged(directory)
            response = PlannedNaturalActionExecutor.execute(assistant, thought)

        self.assertIn("Sprawdziłem nowy termin", response)
        self.assertEqual(len(online.calendar.updated), 1)

    def test_b171_status_and_source_bounds(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=self.events()),
            )
            status = service.status()
        self.assertEqual(
            status["stages"]["B171"],
            "STALE_CALENDAR_PLAN_GUARD_READY",
        )
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/calendar_plan_guard.py": 140,
            "app/natural_actions/service.py": 320,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

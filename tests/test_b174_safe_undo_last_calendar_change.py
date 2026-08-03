from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.gui.repeated_confirmation import (
    remember_confirmed_calendar_write,
    repeated_calendar_confirmation,
)
from app.natural_actions.calendar_undo import CalendarUndoStaleError
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class B174SafeUndoLastCalendarChangeTests(unittest.TestCase):
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

    def moved(self, directory):
        online = FakeOnline(directory, events=self.events())
        service = NaturalActionService(directory, online=online)
        service.handle("Co mam zrobić z tym konfliktem?")
        move = service.plan("Zrób to.")
        assistant = SimpleNamespace(natural_actions=service)
        PlannedNaturalActionExecutor.execute(assistant, move)
        return service, online, assistant

    def test_undo_phrase_is_routed_as_confirmed_calendar_write(self):
        with TemporaryDirectory() as directory:
            service, _online, _assistant = self.moved(directory)
            thought = service.plan("Cofnij to.")
        self.assertEqual(thought["assistant_intent"], "active_undo_calendar")
        self.assertTrue(thought["requires_confirmation"])
        self.assertFalse(thought["read_only"])
        self.assertIn("Spotkanie B", thought["confirmation_message"])
        self.assertIn("18:45", thought["confirmation_message"])

    def test_confirmed_undo_restores_original_time_and_verifies_live_result(self):
        with TemporaryDirectory() as directory:
            service, online, assistant = self.moved(directory)
            undo = service.plan("Cofnij to")
            response = PlannedNaturalActionExecutor.execute(assistant, undo)
            event = next(item for item in online.calendar.events if item["id"] == "event-b")
        self.assertIn("Cofnąłem ostatnią zmianę", response)
        self.assertIn("Sprawdziłem wynik w Google Calendar", response)
        self.assertEqual(datetime.fromisoformat(event["start_at"]).minute, 45)
        self.assertEqual(len(online.calendar.updated), 2)

    def test_manual_change_after_move_blocks_undo_before_write(self):
        with TemporaryDirectory() as directory:
            service, online, _assistant = self.moved(directory)
            event = next(item for item in online.calendar.events if item["id"] == "event-b")
            manual = datetime.fromisoformat(event["start_at"]) + timedelta(minutes=20)
            event["start_at"] = manual.isoformat()
            event["end_at"] = (manual + timedelta(hours=1)).isoformat()
            thought = service.plan("Cofnij to")
            response = service.handle("Cofnij to")
        self.assertFalse(thought["requires_confirmation"])
        self.assertTrue(thought["read_only"])
        self.assertIn("zostało później zmienione", response)
        self.assertEqual(len(online.calendar.updated), 1)

    def test_change_between_confirmation_and_execution_is_rejected(self):
        with TemporaryDirectory() as directory:
            service, online, assistant = self.moved(directory)
            undo = service.plan("Cofnij to")
            event = next(item for item in online.calendar.events if item["id"] == "event-b")
            manual = datetime.fromisoformat(event["start_at"]) + timedelta(minutes=10)
            event["start_at"] = manual.isoformat()
            event["end_at"] = (manual + timedelta(hours=1)).isoformat()
            with self.assertRaises(CalendarUndoStaleError):
                PlannedNaturalActionExecutor.execute(assistant, undo)
        self.assertEqual(len(online.calendar.updated), 1)

    def test_repeated_undo_confirmation_never_writes_twice(self):
        with TemporaryDirectory() as directory:
            service, online, assistant = self.moved(directory)
            undo = service.plan("Cofnij to")
            first = PlannedNaturalActionExecutor.execute(assistant, undo)
            second = PlannedNaturalActionExecutor.execute(assistant, undo)
        self.assertIn("Cofnąłem", first)
        self.assertEqual(
            second,
            "Ta zmiana została już cofnięta. Nie wykonałem jej ponownie.",
        )
        self.assertEqual(len(online.calendar.updated), 2)

    def test_no_verified_move_returns_clear_message_without_confirmation(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory, online=FakeOnline(directory, events=self.events())
            )
            thought = service.plan("Cofnij to")
            response = service.handle("Cofnij to")
        self.assertFalse(thought["requires_confirmation"])
        self.assertTrue(thought["read_only"])
        self.assertEqual(
            response,
            "Nie mam ostatniej zweryfikowanej zmiany kalendarza do cofnięcia.",
        )

    def test_client_owner_priority_builds_exact_undo_plan_before_global_router(self):
        with TemporaryDirectory() as directory:
            service, _online, _assistant = self.moved(directory)
            window = SimpleNamespace(
                assistant=SimpleNamespace(natural_actions=service)
            )
            thought = active_resolution_priority_thought(window, "Cofnij to.")
        self.assertIsNotNone(thought)
        self.assertEqual(thought["assistant_intent"], "active_undo_calendar")
        self.assertTrue(thought["requires_confirmation"])

    def test_repeated_confirmation_bridge_keeps_exact_undo_plan(self):
        thought = {
            "natural_action": True,
            "assistant_intent": "active_undo_calendar",
            "read_only": False,
            "operation_fingerprint": "undo-plan",
        }
        window = SimpleNamespace()
        remember_confirmed_calendar_write(window, thought)
        self.assertEqual(repeated_calendar_confirmation(window, "TAK"), thought)

    def test_b174_status_and_source_bounds(self):
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory, online=FakeOnline(directory, events=self.events())
            )
            status = service.status()
        self.assertEqual(
            status["stages"]["B174"],
            "SAFE_UNDO_LAST_CALENDAR_CHANGE_READY",
        )
        self.assertTrue(status["active_resolution"]["safe_undo"])
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/active_understanding.py": 150,
            "app/natural_actions/calendar_safe_retry.py": 310,
            "app/natural_actions/calendar_undo.py": 220,
            "app/natural_actions/runtime.py": 140,
            "app/natural_actions/service.py": 320,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class B1742ConfirmedUndoPlanPersistenceTests(unittest.TestCase):
    @staticmethod
    def events():
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

    @staticmethod
    def execute(service, thought):
        assistant = SimpleNamespace(natural_actions=service)
        return PlannedNaturalActionExecutor.execute(assistant, thought)

    def move(self, service):
        service.handle("Co mam zrobić z tym konfliktem?")
        thought = service.plan("Zrób to.")
        response = self.execute(service, thought)
        self.assertIn("Przeniosłem", response)
        return thought

    def test_undo_plan_survives_lost_conversation_history(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=self.events())
            service = NaturalActionService(directory, online=online)
            self.move(service)
            data = service.context.load()
            data["history"] = []
            data["last_actions"] = {}
            service.context.store.save(data)

            restarted = NaturalActionService(directory, online=online)
            thought = restarted.plan("Cofnij to.")
            response = self.execute(restarted, thought)

        self.assertEqual(thought["assistant_intent"], "active_undo_calendar")
        self.assertTrue(thought["requires_confirmation"])
        self.assertIn("Cofnąłem ostatnią zmianę", response)
        self.assertEqual(len(online.calendar.updated), 2)

    def test_client_priority_recovers_exact_undo_from_persistent_receipt(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=self.events())
            service = NaturalActionService(directory, online=online)
            self.move(service)
            data = service.context.load()
            data["history"] = []
            service.context.store.save(data)
            restarted = NaturalActionService(directory, online=online)
            window = SimpleNamespace(
                assistant=SimpleNamespace(natural_actions=restarted)
            )

            thought = active_resolution_priority_thought(window, "Cofnij to")

        self.assertIsNotNone(thought)
        self.assertEqual(thought["assistant_intent"], "active_undo_calendar")
        self.assertTrue(thought["requires_confirmation"])
        self.assertTrue(thought["operation_fingerprint"])

    def test_same_move_can_be_executed_again_after_verified_undo(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=self.events())
            service = NaturalActionService(directory, online=online)
            first_move = self.move(service)
            first_undo = service.plan("Cofnij to")
            self.execute(service, first_undo)

            service.handle("Co mam zrobić z tym konfliktem?")
            second_move = service.plan("Zrób to")
            second_response = self.execute(service, second_move)
            second_undo = service.plan("Cofnij to")
            final_response = self.execute(service, second_undo)

        self.assertEqual(
            first_move["operation_fingerprint"],
            second_move["operation_fingerprint"],
        )
        self.assertIn("Przeniosłem", second_response)
        self.assertIn("Cofnąłem ostatnią zmianę", final_response)
        self.assertEqual(len(online.calendar.updated), 4)

    def test_owner_main_window_no_longer_bypasses_exact_executor(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/main_window.py").read_text(encoding="utf-8")
        method = source.split("def handle_confirmation", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("handle_owner_confirmation(self, answer)", method)
        self.assertNotIn("self.brain.execute(pending)", method)

    def test_b174_2_source_bounds(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/active_resolution.py": 360,
            "app/natural_actions/calendar_safe_retry.py": 310,
            "app/natural_actions/calendar_undo.py": 220,
            "app/natural_actions/context.py": 230,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

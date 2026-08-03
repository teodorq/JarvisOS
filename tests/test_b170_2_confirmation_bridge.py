from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.ai.brain_command_router import BrainCommandRouter
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class _Brain:
    def __init__(self, assistant):
        self.personal_assistant_controller = assistant
        self.remembered = []

    def _remember_execution(self, command, result):
        self.remembered.append((command, result))


class _Assistant:
    def __init__(self, natural_actions):
        self.natural_actions = natural_actions
        self.handled = []

    def handle(self, command):
        self.handled.append(command)
        return "LEGACY_OK"


class B1702ConfirmationBridgeTests(unittest.TestCase):
    def events(self):
        now = datetime.now().astimezone().replace(microsecond=0)
        start = (now + timedelta(days=1)).replace(
            hour=18, minute=0, second=0
        )
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

    def test_confirmed_thought_executes_exact_planned_calendar_write(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=self.events())
            service = NaturalActionService(directory, online=online)
            service.handle("Co mam zrobić z tym konfliktem?")
            thought = service.plan("Zrób to")
            service.runtime.active.memory.clear_suggestion()

            assistant = _Assistant(service)
            brain = _Brain(assistant)
            result = BrainCommandRouter().execute(brain, thought)

        self.assertIn("Przeniosłem", result)
        self.assertIn("Google Calendar", result)
        self.assertEqual(len(online.calendar.updated), 1)
        self.assertEqual(
            online.calendar.updated[0]["event_id"],
            thought["natural_slots"]["event_id"],
        )
        self.assertEqual(assistant.handled, [])

    def test_planned_slots_survive_confirmation_without_reparse(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=self.events())
            service = NaturalActionService(directory, online=online)
            service.handle("Co mam zrobić z tym konfliktem?")
            thought = service.plan("Zrób to")
            expected_when = thought["natural_slots"]["new_when"]
            service.runtime.active.memory.clear_suggestion()
            service.context.clear_pending()

            BrainCommandRouter().execute(
                _Brain(_Assistant(service)),
                thought,
            )

        self.assertEqual(
            online.calendar.updated[0]["start_at"].isoformat(),
            expected_when,
        )

    def test_tampered_confirmed_plan_is_blocked_before_calendar_write(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory, events=self.events())
            service = NaturalActionService(directory, online=online)
            service.handle("Co mam zrobić z tym konfliktem?")
            thought = service.plan("Zrób to")
            thought["natural_slots"]["event_id"] = "other-event"

            with self.assertRaisesRegex(ValueError, "changed"):
                BrainCommandRouter().execute(
                    _Brain(_Assistant(service)),
                    thought,
                )

        self.assertEqual(online.calendar.updated, [])

    def test_non_natural_personal_assistant_flow_remains_compatible(self):
        assistant = _Assistant(SimpleNamespace())
        brain = _Brain(assistant)
        thought = {
            "handler": "personal_assistant",
            "command": "status asystenta",
        }

        result = BrainCommandRouter().execute(brain, thought)

        self.assertEqual(result, "LEGACY_OK")
        self.assertEqual(assistant.handled, ["status asystenta"])

    def test_source_limits_and_bridge_marker(self):
        root = Path(__file__).resolve().parents[1]
        router = (root / "app/ai/brain_command_router.py").read_text(
            encoding="utf-8"
        )
        bridge = (root / "app/natural_actions/planned_execution.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("PlannedNaturalActionExecutor.execute", router)
        self.assertLess(len(router.splitlines()), 200)
        self.assertLess(len(bridge.splitlines()), 90)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import types
import unittest

try:
    from app.gui import client_command_runtime as runtime_module
except ModuleNotFoundError as error:
    if error.name not in {"PySide6", "PySide6.QtCore"}:
        raise
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QTimer = type("QTimer", (), {})
    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore
    from app.gui import client_command_runtime as runtime_module

from app.gui.confirmation_revision_runtime import handle_owner_confirmation
from app.jarvis_experience.smart_task_loop import SmartTaskLoop
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


ClientCommandRuntimeMixin = runtime_module.ClientCommandRuntimeMixin


class _ImmediateTimer:
    @staticmethod
    def singleShot(_delay, callback):
        callback()


class _Signal:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(dict(event))


class _Access:
    @staticmethod
    def authorize(_command, read_only=False):
        return {"allowed": True}


class _BrainThatMustNotRouteCalendar:
    def __init__(self, assistant):
        self.personal_assistant_controller = assistant
        self.execute_calls = []

    def execute(self, thought):
        self.execute_calls.append(dict(thought))
        return "B174 controller internal result"


class _Client(ClientCommandRuntimeMixin):
    def __init__(self, assistant):
        self.assistant = assistant
        self.brain = _BrainThatMustNotRouteCalendar(assistant)
        self.pending_thought = None
        self.client_event_signal = _Signal()
        self.business_service = SimpleNamespace(access_control=_Access())
        self.spoken = []

    @staticmethod
    def is_safe_thought(thought):
        return bool(thought.get("read_only", False))

    def say_safe(self, text):
        self.spoken.append(str(text))


class _Console:
    def __init__(self):
        self.lines = []
        self.states = []

    def append(self, text):
        self.lines.append(str(text))

    def set_state(self, label, style):
        self.states.append((label, style))


class _Owner:
    def __init__(self, assistant, pending):
        self.assistant = assistant
        self.brain = _BrainThatMustNotRouteCalendar(assistant)
        self.pending_thought = dict(pending)
        self.console_page = _Console()
        self.spoken = []

    def say_safe(self, text):
        self.spoken.append(str(text))


def _events(title="Spotkanie B"):
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
            "title": title,
            "start_at": (start + timedelta(minutes=45)).isoformat(),
            "end_at": (start + timedelta(minutes=105)).isoformat(),
        },
    ]


def _moved(directory, *, title="Spotkanie B"):
    online = FakeOnline(directory, events=_events(title))
    service = NaturalActionService(directory, online=online)
    service.handle("Co mam zrobić z tym konfliktem?")
    move = service.plan("Zrób to.")
    assistant = SimpleNamespace(natural_actions=service)
    PlannedNaturalActionExecutor.execute(assistant, move)
    return service, online, assistant


class B1741RuntimeUndoExecutionRoutingTests(unittest.TestCase):
    def setUp(self):
        self.original_timer = runtime_module.QTimer
        runtime_module.QTimer = _ImmediateTimer

    def tearDown(self):
        runtime_module.QTimer = self.original_timer

    def test_client_executes_exact_undo_without_global_brain_route(self):
        with TemporaryDirectory() as directory:
            service, online, assistant = _moved(
                directory, title="Spotkanie B174"
            )
            client = _Client(assistant)

            client.process_client_command("Cofnij to.")
            self.assertEqual(
                client.pending_thought["assistant_intent"],
                "active_undo_calendar",
            )
            client.process_client_command("TAK")

            event = next(
                item for item in online.calendar.events
                if item["id"] == "event-b"
            )
        self.assertEqual(client.brain.execute_calls, [])
        self.assertEqual(datetime.fromisoformat(event["start_at"]).minute, 45)
        self.assertEqual(len(online.calendar.updated), 2)
        message = client.client_event_signal.events[-1]["message"]
        self.assertIn("Cofnąłem ostatnią zmianę", message)
        self.assertIn("Spotkanie B174", message)
        self.assertIn("Sprawdziłem wynik w Google Calendar", message)
        self.assertNotEqual(message, "Zadanie zostało obsłużone.")

    def test_calendar_title_with_stage_like_text_is_not_hidden(self):
        thought = {
            "natural_action": True,
            "assistant_intent": "active_undo_calendar",
        }
        loop = SmartTaskLoop(
            SimpleNamespace(execute=lambda _thought: None),
            lambda _command, _read_only: {"allowed": True},
            lambda _thought: True,
        )
        outcome = loop.execute(
            thought,
            executor=lambda _thought: (
                "Cofnąłem ostatnią zmianę. „Spotkanie B174” jest jutro "
                "o 18:45. Sprawdziłem wynik w Google Calendar."
            ),
        )
        self.assertEqual(outcome.status, "COMPLETED")
        self.assertIn("Spotkanie B174", outcome.message)
        self.assertNotEqual(outcome.message, "Zadanie zostało obsłużone.")

    def test_owner_confirmation_uses_the_same_exact_undo_executor(self):
        with TemporaryDirectory() as directory:
            _service, online, assistant = _moved(directory)
            undo = assistant.natural_actions.plan("Cofnij to")
            owner = _Owner(assistant, undo)

            handle_owner_confirmation(owner, "TAK")

            event = next(
                item for item in online.calendar.events
                if item["id"] == "event-b"
            )
        self.assertEqual(owner.brain.execute_calls, [])
        self.assertEqual(datetime.fromisoformat(event["start_at"]).minute, 45)
        self.assertIn("Cofnąłem ostatnią zmianę", owner.spoken[-1])
        self.assertEqual(
            owner.console_page.states[-1],
            ("GOTOWY NA POLECENIE", "healthy"),
        )

    def test_non_calendar_plan_keeps_existing_brain_route(self):
        assistant = SimpleNamespace(natural_actions=None)
        client = _Client(assistant)
        thought = {
            "handler": "standard",
            "can_execute": True,
            "read_only": True,
        }

        client._execute_client_thought(thought)

        self.assertEqual(client.brain.execute_calls, [thought])

    def test_source_bounds_and_no_hardcoded_project_root(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/confirmed_calendar_execution.py": 80,
            "app/gui/client_command_runtime.py": 180,
            "app/gui/business_command_runtime.py": 180,
            "app/gui/confirmation_revision_runtime.py": 100,
            "app/jarvis_experience/smart_task_loop.py": 130,
            "app/jarvis_experience/isolation.py": 100,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
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
from app.gui.repeated_confirmation import repeated_calendar_confirmation
from app.natural_actions.models import NaturalActionRequest
from app.natural_actions.runtime import NaturalActionRuntime

ClientCommandRuntimeMixin = runtime_module.ClientCommandRuntimeMixin
MESSAGE = "Ta zmiana została już wykonana. Nie wykonałem jej ponownie."


class _ImmediateTimer:
    @staticmethod
    def singleShot(_delay, callback):
        callback()


class _Signal:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(dict(event))


class _Brain:
    def __init__(self):
        self.executed = []
        self.think_calls = []

    def think(self, command):
        self.think_calls.append(command)
        return {"can_execute": False}

    def execute(self, thought):
        self.executed.append(dict(thought))
        return (
            "Przeniosłem wydarzenie."
            if len(self.executed) == 1 else MESSAGE
        )


class _Access:
    def authorize(self, _command, read_only=False):
        return {"allowed": True}


class _Client(ClientCommandRuntimeMixin):
    def __init__(self):
        self.pending_thought = None
        self.client_event_signal = _Signal()
        self.brain = _Brain()
        self.business_service = SimpleNamespace(access_control=_Access())
        self.spoken = []

    @staticmethod
    def is_safe_thought(_thought):
        return False

    def say_safe(self, text):
        self.spoken.append(text)


class _Console:
    def __init__(self):
        self.lines = []
        self.states = []

    def append(self, value):
        self.lines.append(value)

    def set_state(self, label, style):
        self.states.append((label, style))


class _Owner:
    def __init__(self, thought):
        self.pending_thought = dict(thought)
        self.brain = _Brain()
        self.console_page = _Console()
        self.spoken = []

    def say_safe(self, text):
        self.spoken.append(text)


def _thought():
    return {
        "handler": "personal_assistant",
        "natural_action": True,
        "assistant_intent": "active_apply_suggestion",
        "natural_slots": {"event_id": "event-b"},
        "operation_fingerprint": "exact-calendar-plan",
        "can_execute": True,
        "read_only": False,
    }


class B1731DuplicateUserMessageTests(unittest.TestCase):
    def setUp(self):
        self.original_timer = runtime_module.QTimer
        runtime_module.QTimer = _ImmediateTimer

    def tearDown(self):
        runtime_module.QTimer = self.original_timer

    def test_client_second_yes_reuses_exact_plan_and_shows_clear_message(self):
        client = _Client()
        thought = _thought()
        client._execute_client_thought(thought)

        client.process_client_command("TAK")

        self.assertEqual(client.brain.executed, [thought, thought])
        self.assertEqual(client.brain.think_calls, [])
        self.assertEqual(client.client_event_signal.events[-1]["state"], "success")
        self.assertEqual(client.client_event_signal.events[-1]["message"], MESSAGE)

    def test_owner_confirmation_remembers_same_plan_for_second_yes(self):
        thought = _thought()
        owner = _Owner(thought)

        handle_owner_confirmation(owner, "TAK")

        self.assertEqual(repeated_calendar_confirmation(owner, "TAK"), thought)
        self.assertIsNone(owner.pending_thought)

    def test_runtime_returns_exact_duplicate_calendar_message(self):
        request = NaturalActionRequest(
            original="Zrób to.", command="Zrób to.",
            intent="active_apply_suggestion", confidence=1.0,
            slots={"event_id": "event-b"}, missing=[],
            clarification="", confirmation="", read_only=False,
        )
        runtime = NaturalActionRuntime.__new__(NaturalActionRuntime)
        runtime.context = SimpleNamespace(
            execution_result=lambda _fingerprint: "Pierwszy sukces."
        )

        self.assertEqual(runtime.execute_once(request), MESSAGE)

    def test_repeated_no_is_not_treated_as_duplicate_acceptance(self):
        owner = _Owner(_thought())
        handle_owner_confirmation(owner, "TAK")
        self.assertIsNone(repeated_calendar_confirmation(owner, "NIE"))

    def test_client_source_routes_repeat_before_global_plan(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/client_command_runtime.py").read_text(
            encoding="utf-8"
        )
        repeated = source.index("repeated_calendar_confirmation(self, value)")
        global_plan = source.index("self._client_task_loop().plan(value)")
        self.assertLess(repeated, global_plan)
        self.assertLess(len(source.splitlines()), 190)


if __name__ == "__main__":
    unittest.main()

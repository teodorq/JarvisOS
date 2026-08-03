from __future__ import annotations

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

ClientCommandRuntimeMixin = runtime_module.ClientCommandRuntimeMixin
MESSAGE = "Ta zmiana została już wykonana. Nie wykonałem jej ponownie."


class _DeferredTimer:
    callbacks = []

    @classmethod
    def singleShot(cls, _delay, callback):
        cls.callbacks.append(callback)


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
        return "Przeniosłem wydarzenie." if len(self.executed) == 1 else MESSAGE


class _Access:
    @staticmethod
    def authorize(_command, read_only=False):
        return {"allowed": True}


class _Client(ClientCommandRuntimeMixin):
    def __init__(self, thought):
        self.pending_thought = dict(thought)
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
    def append(self, _value):
        pass

    def set_state(self, _label, _style):
        pass


class _InspectingBrain:
    def __init__(self, window):
        self.window = window
        self.seen_during_execute = None

    def execute(self, _thought):
        self.seen_during_execute = repeated_calendar_confirmation(
            self.window, "TAK"
        )
        return "Przeniosłem wydarzenie."


class _Owner:
    def __init__(self, thought):
        self.pending_thought = dict(thought)
        self.console_page = _Console()
        self.spoken = []
        self.brain = _InspectingBrain(self)

    def say_safe(self, text):
        self.spoken.append(text)


def _thought():
    return {
        "handler": "personal_assistant",
        "natural_action": True,
        "assistant_intent": "active_apply_suggestion",
        "natural_slots": {
            "event_id": "event-b",
            "event_title": "Spotkanie B",
            "new_when": "2026-07-31T19:00:00+02:00",
        },
        "operation_fingerprint": "exact-calendar-plan",
        "can_execute": True,
        "read_only": False,
    }


class B1732RuntimeDuplicateMessageRoutingTests(unittest.TestCase):
    def setUp(self):
        self.original_timer = runtime_module.QTimer
        runtime_module.QTimer = _DeferredTimer
        _DeferredTimer.callbacks = []

    def tearDown(self):
        runtime_module.QTimer = self.original_timer
        _DeferredTimer.callbacks = []

    def test_client_confirmation_is_cached_before_delayed_live_execution(self):
        thought = _thought()
        client = _Client(thought)

        client.process_client_command("TAK")

        self.assertEqual(
            repeated_calendar_confirmation(client, "TAK"), thought
        )
        self.assertEqual(client.brain.executed, [])
        self.assertEqual(len(_DeferredTimer.callbacks), 1)

    def test_second_yes_during_live_verification_reuses_exact_plan(self):
        thought = _thought()
        client = _Client(thought)

        client.process_client_command("TAK")
        client.process_client_command("TAK")

        self.assertEqual(client.brain.think_calls, [])
        self.assertEqual(len(_DeferredTimer.callbacks), 2)
        while _DeferredTimer.callbacks:
            _DeferredTimer.callbacks.pop(0)()
        self.assertEqual(client.brain.executed, [thought, thought])
        self.assertEqual(client.client_event_signal.events[-1]["state"], "success")
        self.assertEqual(client.client_event_signal.events[-1]["message"], MESSAGE)

    def test_owner_confirmation_is_cached_before_brain_execute(self):
        thought = _thought()
        owner = _Owner(thought)

        handle_owner_confirmation(owner, "TAK")

        self.assertEqual(owner.brain.seen_during_execute, thought)
        self.assertIsNone(owner.pending_thought)


if __name__ == "__main__":
    unittest.main()

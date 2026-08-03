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
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = []

    def authorize(self, command, read_only=False):
        self.calls.append((command, read_only))
        return {"allowed": self.allowed}


class _Memory:
    def last_suggestion(self):
        return {"kind": "calendar_move", "event_id": "event-b"}


class _Natural:
    def __init__(self):
        self.runtime = SimpleNamespace(
            active=SimpleNamespace(memory=_Memory())
        )
        self.commands = []

    def plan(self, command):
        self.commands.append(command)
        return {
            "handler": "personal_assistant",
            "natural_action": True,
            "assistant_intent": "active_apply_suggestion",
            "natural_slots": {
                "event_id": "event-b",
                "new_when": "2026-07-30T19:00:00+02:00",
            },
            "operation_fingerprint": "exact-plan",
            "can_execute": True,
            "read_only": False,
            "requires_confirmation": True,
            "confirmation_message": (
                "Przenieść „Spotkanie B” na jutro o 19:00?"
            ),
        }


class _Brain:
    def __init__(self):
        self.think_calls = []
        self.executed = []

    def think(self, command):
        self.think_calls.append(command)
        raise AssertionError("Global router must not receive active apply")

    def execute(self, thought):
        self.executed.append(dict(thought))
        return "Przeniosłem „Spotkanie B” na jutro o 19:00."


class _Window(ClientCommandRuntimeMixin):
    def __init__(self, *, allowed=True):
        self.pending_thought = None
        self.client_event_signal = _Signal()
        self.brain = _Brain()
        self.assistant = SimpleNamespace(natural_actions=_Natural())
        self.business_service = SimpleNamespace(
            access_control=_Access(allowed)
        )
        self.spoken = []

    @staticmethod
    def is_safe_thought(_thought):
        return False

    def say_safe(self, text):
        self.spoken.append(text)


class B1705ClientConfirmationParityTests(unittest.TestCase):
    def setUp(self):
        self.original_timer = runtime_module.QTimer
        runtime_module.QTimer = _ImmediateTimer

    def tearDown(self):
        runtime_module.QTimer = self.original_timer

    def test_client_apply_stages_exact_plan_and_requests_confirmation(self):
        window = _Window()
        window.process_client_command("Zrób to.")

        self.assertIsNotNone(window.pending_thought)
        self.assertEqual(
            window.pending_thought["assistant_intent"],
            "active_apply_suggestion",
        )
        self.assertEqual(window.brain.think_calls, [])
        self.assertEqual(
            window.assistant.natural_actions.commands,
            ["Zrób to."],
        )
        event = window.client_event_signal.events[-1]
        self.assertEqual(event["state"], "warning")
        self.assertTrue(event["requires_confirmation"])
        self.assertIn("Spotkanie B", event["message"])
        self.assertEqual(
            window.business_service.access_control.calls,
            [("Zrób to.", False)],
        )

    def test_client_yes_executes_the_same_staged_plan_once(self):
        window = _Window()
        window.process_client_command("Zrób to.")
        staged = dict(window.pending_thought)

        window.process_client_command("TAK")

        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.brain.executed, [staged])
        self.assertEqual(window.brain.think_calls, [])
        self.assertEqual(
            window.client_event_signal.events[-1]["state"],
            "success",
        )

    def test_client_denial_does_not_stage_or_execute_write(self):
        window = _Window(allowed=False)
        window.process_client_command("Zrób to!")

        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.brain.executed, [])
        event = window.client_event_signal.events[-1]
        self.assertEqual(event["state"], "error")
        self.assertIn("uprawnień", event["message"])

    def test_client_runtime_checks_priority_before_global_plan(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/gui/client_command_runtime.py").read_text(
            encoding="utf-8"
        )
        priority = source.index(
            "active_resolution_priority_thought(self, value)"
        )
        global_plan = source.index("self._client_task_loop().plan(value)")
        self.assertLess(priority, global_plan)
        self.assertIn("requires_confirmation=True", source)
        self.assertLess(len(source.splitlines()), 180)


if __name__ == "__main__":
    unittest.main()

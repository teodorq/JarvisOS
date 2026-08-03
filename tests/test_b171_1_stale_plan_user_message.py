from __future__ import annotations

from types import SimpleNamespace
import unittest

from app.gui.confirmation_revision_runtime import handle_owner_confirmation
from app.jarvis_experience.smart_task_loop import SmartTaskLoop
from app.natural_actions.calendar_plan_guard import CalendarPlanStaleError


MESSAGE = (
    "Plan zmiany kalendarza jest już nieaktualny. "
    "Nie wykonałem zmiany. Poproś mnie o ponowne sprawdzenie konfliktu."
)


class _ClientBrain:
    def __init__(self, error: Exception):
        self.error = error

    def execute(self, _thought):
        raise self.error


class _Console:
    def __init__(self):
        self.lines = []
        self.states = []

    def append(self, text):
        self.lines.append(text)

    def set_state(self, label, style):
        self.states.append((label, style))


class _OwnerWindow:
    def __init__(self):
        self.pending_thought = {"handler": "personal_assistant"}
        self.brain = _ClientBrain(CalendarPlanStaleError(MESSAGE))
        self.console_page = _Console()
        self.spoken = []

    def say_safe(self, text):
        self.spoken.append(text)


class B1711StalePlanUserMessageTests(unittest.TestCase):
    def test_client_receives_specific_safe_stale_plan_message(self):
        loop = SmartTaskLoop(
            _ClientBrain(CalendarPlanStaleError(MESSAGE)),
            lambda _command, _read_only: {"allowed": True},
            lambda _thought: True,
        )

        outcome = loop.execute({"handler": "personal_assistant"})

        self.assertEqual(outcome.status, "STALE_PLAN")
        self.assertEqual(outcome.message, MESSAGE)
        self.assertNotIn("Spróbuj ponownie", outcome.message)

    def test_unrelated_execution_error_stays_generic(self):
        loop = SmartTaskLoop(
            _ClientBrain(RuntimeError("secret technical path C:/JarvisAI")),
            lambda _command, _read_only: {"allowed": True},
            lambda _thought: True,
        )

        outcome = loop.execute({"handler": "personal_assistant"})

        self.assertEqual(outcome.status, "FAILED")
        self.assertEqual(
            outcome.message,
            "Nie udało się zakończyć zadania. Spróbuj ponownie.",
        )
        self.assertNotIn("C:/JarvisAI", outcome.message)

    def test_owner_confirmation_shows_same_stale_plan_message(self):
        window = _OwnerWindow()

        handle_owner_confirmation(window, "TAK")

        self.assertIsNone(window.pending_thought)
        self.assertEqual(window.spoken, [MESSAGE])
        self.assertEqual(
            window.console_page.states[-1],
            ("PLAN NIEAKTUALNY", "danger"),
        )
        self.assertEqual(window.console_page.lines[-1], "Jarvis: " + MESSAGE)

    def test_exception_remains_value_error_compatible(self):
        self.assertTrue(issubclass(CalendarPlanStaleError, ValueError))


if __name__ == "__main__":
    unittest.main()

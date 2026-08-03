from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.ai.actions import ActionTypes
from app.assistant.reliable_desktop import ReliableDesktopService


class _Executor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def execute_action(self, action):
        self.calls += 1
        value = self.results[min(self.calls - 1, len(self.results) - 1)]
        if isinstance(value, Exception):
            raise value
        return value


class B97ReliableDesktopTests(unittest.TestCase):

    def test_idempotent_action_retries_once_after_failure(self) -> None:
        with TemporaryDirectory() as temporary:
            executor = _Executor(["Błąd otwierania", "Otwieram Notatnik."])
            windows = iter([[], [], [], ["Notatnik"]])
            service = ReliableDesktopService(
                temporary,
                retry_delay=0,
                window_probe=lambda: next(windows, ["Notatnik"]),
            )
            result = service.execute_action(
                {"action_type": ActionTypes.OPEN_APP, "target": "notatnik"},
                executor,
            )
            self.assertEqual(executor.calls, 2)
            self.assertIn("potwierdzono", result)
            self.assertEqual(service.status()["success_count"], 1)

    def test_non_idempotent_typing_is_never_retried(self) -> None:
        with TemporaryDirectory() as temporary:
            executor = _Executor([RuntimeError("awaria")])
            service = ReliableDesktopService(temporary, retry_delay=0)
            result = service.execute_action(
                {"action_type": ActionTypes.TYPE_TEXT, "text": "test"},
                executor,
            )
            self.assertEqual(executor.calls, 1)
            self.assertIn("1 próbie", result)
            self.assertEqual(service.status()["failure_count"], 1)

    def test_successful_non_window_action_is_verified(self) -> None:
        with TemporaryDirectory() as temporary:
            service = ReliableDesktopService(temporary)
            result = service.execute_action(
                {"action_type": ActionTypes.PRESS_ENTER},
                _Executor(["Naciśnięto Enter."]),
            )
            self.assertIn("potwierdzono", result)

    def test_memory_actions_are_not_misclassified_as_desktop(self) -> None:
        service = ReliableDesktopService.supports
        self.assertFalse(service({"action_type": ActionTypes.REMEMBER}))
        self.assertFalse(service({"action_type": ActionTypes.MEMORY_SUMMARY}))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.ai.actions import ActionTypes
from app.intelligence.desktop_orchestrator import DesktopAgentV2


class _Executor:
    def __init__(self, result: str = "Naciśnięto Enter.") -> None:
        self.result = result
        self.calls = 0

    def execute_action(self, action):
        self.calls += 1
        return self.result


class B103DesktopAgent2Tests(unittest.TestCase):

    def test_verified_transaction_is_persistent(self) -> None:
        with TemporaryDirectory() as temporary:
            service = DesktopAgentV2(temporary)
            result = service.execute_action(
                {"action_type": ActionTypes.PRESS_ENTER},
                _Executor(),
            )
            self.assertIn("potwierdzono", result)
            reloaded = DesktopAgentV2(temporary)
            self.assertEqual(reloaded.status()["verified_count"], 1)

    def test_fast_duplicate_typing_is_blocked(self) -> None:
        with TemporaryDirectory() as temporary:
            service = DesktopAgentV2(temporary, duplicate_window_seconds=30)
            executor = _Executor("Wpisano tekst.")
            action = {"action_type": ActionTypes.TYPE_TEXT, "text": "abc"}
            service.execute_action(action, executor)
            result = service.execute_action(action, executor)
            self.assertIn("zablokowano", result)
            self.assertEqual(executor.calls, 1)
            self.assertEqual(service.status()["duplicate_blocks"], 1)

    def test_memory_action_is_not_supported(self) -> None:
        self.assertFalse(
            DesktopAgentV2.supports({"action_type": ActionTypes.REMEMBER})
        )


if __name__ == "__main__":
    unittest.main()

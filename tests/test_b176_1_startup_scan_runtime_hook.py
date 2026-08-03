from __future__ import annotations

from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch

try:
    from PySide6.QtCore import QTimer as _QtTimer  # noqa: F401
except ModuleNotFoundError:
    pyside = ModuleType("PySide6")
    qtcore = ModuleType("PySide6.QtCore")
    qtcore.QTimer = object
    pyside.QtCore = qtcore
    sys.modules.setdefault("PySide6", pyside)
    sys.modules.setdefault("PySide6.QtCore", qtcore)

from app.gui.client_startup_conflict_runtime import ClientStartupConflictRuntime


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class FakeTimer:
    single_shots = []

    def __init__(self, _parent=None) -> None:
        self.timeout = _Signal()
        self.active = False
        self.starts = []

    def setSingleShot(self, _value) -> None:
        return

    def isActive(self) -> bool:
        return self.active

    def start(self, milliseconds: int) -> None:
        self.active = True
        self.starts.append(milliseconds)

    def stop(self) -> None:
        self.active = False

    def fire(self) -> None:
        self.active = False
        self.timeout.callback()

    @classmethod
    def singleShot(cls, milliseconds: int, callback) -> None:
        cls.single_shots.append((milliseconds, callback))


class FakeNatural:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.calls = 0

    def startup_conflict_scan(self):
        self.calls += 1
        value = self.results.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class FakeController:
    def status(self):
        return {"profile": {"setup_completed": True}}


class FakeWindow:
    def __init__(self, natural) -> None:
        self.presenter = SimpleNamespace(busy=False)
        self.owner_window = SimpleNamespace(
            pending_thought=None,
            assistant=SimpleNamespace(natural_actions=natural),
        )
        self.controller = FakeController()
        self.events = []
        self.briefs = 0

    def _on_client_event(self, event) -> None:
        self.events.append(dict(event))

    def _show_proactive_brief(self) -> None:
        self.briefs += 1


class B1761StartupScanRuntimeHookTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeTimer.single_shots = []
        self.patcher = patch(
            "app.gui.client_startup_conflict_runtime.QTimer",
            FakeTimer,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    @staticmethod
    def _quiet():
        return {
            "should_show": False,
            "automatic_writes": False,
            "scan_completed": True,
        }

    @staticmethod
    def _conflict():
        return {
            "should_show": True,
            "message": "Wykryłem konflikt. Co mam zrobić z tym konfliktem?",
            "automatic_writes": False,
            "scan_completed": True,
        }

    def test_b176_1_retries_empty_startup_then_shows_conflict(self):
        natural = FakeNatural([self._quiet(), self._conflict()])
        window = FakeWindow(natural)
        runtime = ClientStartupConflictRuntime(window)

        runtime.arm()
        self.assertEqual(runtime.timer.starts, [1200])
        runtime.timer.fire()
        self.assertEqual(runtime.timer.starts[-1], 1800)
        runtime.timer.fire()

        self.assertTrue(runtime.done)
        self.assertEqual(natural.calls, 2)
        self.assertEqual(len(window.events), 1)
        self.assertEqual(window.events[0]["state"], "important")
        self.assertFalse(window.events[0]["requires_confirmation"])

    def test_b176_1_transient_calendar_error_is_retried(self):
        natural = FakeNatural([RuntimeError("not ready"), self._conflict()])
        window = FakeWindow(natural)
        runtime = ClientStartupConflictRuntime(window)

        runtime.arm()
        runtime.timer.fire()
        self.assertFalse(runtime.done)
        runtime.timer.fire()

        self.assertTrue(runtime.done)
        self.assertEqual(len(window.events), 1)

    def test_b176_1_busy_client_does_not_consume_attempt(self):
        natural = FakeNatural([self._conflict()])
        window = FakeWindow(natural)
        runtime = ClientStartupConflictRuntime(window)
        window.presenter.busy = True

        runtime.arm()
        runtime.timer.fire()
        self.assertEqual(runtime.attempt, 0)
        self.assertEqual(runtime.timer.starts[-1], 1200)

        window.presenter.busy = False
        runtime.timer.fire()
        self.assertEqual(runtime.attempt, 1)
        self.assertTrue(runtime.done)

    def test_b176_1_quiet_scan_stops_after_bounded_retries(self):
        natural = FakeNatural([self._quiet()] * 5)
        window = FakeWindow(natural)
        runtime = ClientStartupConflictRuntime(window)

        runtime.arm()
        for _ in range(5):
            runtime.timer.fire()

        self.assertTrue(runtime.done)
        self.assertEqual(natural.calls, 5)
        self.assertEqual(window.events, [])
        self.assertEqual(FakeTimer.single_shots[0][0], 150)

    def test_b176_1_runtime_never_executes_calendar_write(self):
        source = __import__(
            "pathlib"
        ).Path(__file__).resolve().parents[1].joinpath(
            "app/gui/client_startup_conflict_runtime.py"
        ).read_text(encoding="utf-8")
        forbidden = ("create_event(", "update_event(", "delete_event(", "move_event(")
        for marker in forbidden:
            self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()

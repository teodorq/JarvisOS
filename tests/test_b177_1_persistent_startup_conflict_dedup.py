from __future__ import annotations

from pathlib import Path
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


class _Timer:
    single_shots: list[tuple[int, object]] = []

    def __init__(self, _parent=None) -> None:
        self.timeout = _Signal()
        self.active = False
        self.starts: list[int] = []

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


class _Natural:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.calls = 0

    def startup_conflict_scan(self):
        self.calls += 1
        return dict(self.results.pop(0))


class _Controller:
    def status(self):
        return {"profile": {"setup_completed": True}}


class _Window:
    def __init__(self, natural) -> None:
        self.presenter = SimpleNamespace(busy=False)
        self.owner_window = SimpleNamespace(
            pending_thought=None,
            assistant=SimpleNamespace(natural_actions=natural),
        )
        self.controller = _Controller()
        self.events: list[dict] = []
        self.briefs = 0

    def _on_client_event(self, event) -> None:
        self.events.append(dict(event))

    def _show_proactive_brief(self) -> None:
        self.briefs += 1


class B1771PersistentStartupConflictDedupTests(unittest.TestCase):
    def setUp(self) -> None:
        _Timer.single_shots = []
        self.patcher = patch(
            "app.gui.client_startup_conflict_runtime.QTimer",
            _Timer,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    @staticmethod
    def duplicate():
        return {
            "should_show": False,
            "scan_completed": True,
            "duplicate_suppressed": True,
            "notification_reason": "unchanged",
            "automatic_writes": False,
        }

    @staticmethod
    def decision_suppressed():
        return {
            "should_show": False,
            "scan_completed": True,
            "duplicate_suppressed": False,
            "notification_reason": "suppressed_by_decision",
            "automatic_writes": False,
        }

    def test_duplicate_finishes_without_daily_brief_fallback(self):
        natural = _Natural([self.duplicate()])
        window = _Window(natural)
        runtime = ClientStartupConflictRuntime(window)

        runtime.arm()
        runtime.timer.fire()

        self.assertTrue(runtime.done)
        self.assertEqual(natural.calls, 1)
        self.assertEqual(window.events, [])
        self.assertEqual(window.briefs, 0)
        self.assertEqual(_Timer.single_shots, [])

    def test_decision_suppression_cannot_be_bypassed_by_fallback(self):
        natural = _Natural([self.decision_suppressed()])
        window = _Window(natural)
        runtime = ClientStartupConflictRuntime(window)

        runtime.arm()
        runtime.timer.fire()

        self.assertTrue(runtime.done)
        self.assertEqual(window.events, [])
        self.assertEqual(_Timer.single_shots, [])

    def test_new_or_changed_conflict_is_still_delivered(self):
        natural = _Natural([{
            "should_show": True,
            "scan_completed": True,
            "message": "Wykryłem zmieniony konflikt.",
            "notification_reason": "new",
            "automatic_writes": False,
        }])
        window = _Window(natural)
        runtime = ClientStartupConflictRuntime(window)

        runtime.arm()
        runtime.timer.fire()

        self.assertTrue(runtime.done)
        self.assertEqual(len(window.events), 1)
        self.assertEqual(window.events[0]["state"], "important")

    def test_transient_quiet_result_is_still_retried(self):
        natural = _Natural([{
            "should_show": False,
            "scan_completed": True,
            "notification_reason": "quiet",
            "automatic_writes": False,
        }])
        window = _Window(natural)
        runtime = ClientStartupConflictRuntime(window)

        runtime.arm()
        runtime.timer.fire()

        self.assertFalse(runtime.done)
        self.assertEqual(runtime.timer.starts[-1], 1800)

    def test_fix_is_read_only(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "app/gui/client_startup_conflict_runtime.py"
        ).read_text(encoding="utf-8")
        for marker in ("create_event(", "update_event(", "delete_event(", "move_event("):
            self.assertNotIn(marker, source)

    def test_source_bounds(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "app/gui/client_startup_conflict_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 100)


if __name__ == "__main__":
    unittest.main()

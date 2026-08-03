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

from app.gui.client_live_conflict_refresh import (
    ClientLiveConflictRefreshRuntime,
)


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class _Timer:
    def __init__(self, _parent=None) -> None:
        self.timeout = _Signal()
        self.active = False
        self.interval = 0
        self.starts = 0

    def setInterval(self, milliseconds: int) -> None:
        self.interval = milliseconds

    def isActive(self) -> bool:
        return self.active

    def start(self) -> None:
        self.active = True
        self.starts += 1

    def fire(self) -> None:
        self.timeout.callback()


class _Natural:
    def __init__(self, result) -> None:
        self.result = dict(result)
        self.calls = 0

    def startup_conflict_scan(self):
        self.calls += 1
        return dict(self.result)


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
        self.events = []

    def _on_client_event(self, event) -> None:
        self.events.append(dict(event))


class B178LiveConflictRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = patch(
            "app.gui.client_live_conflict_refresh.QTimer",
            _Timer,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    @staticmethod
    def conflict():
        return {
            "should_show": True,
            "message": "Wykryłem zmieniony konflikt.",
            "notification_reason": "new",
            "automatic_writes": False,
        }

    @staticmethod
    def duplicate():
        return {
            "should_show": False,
            "duplicate_suppressed": True,
            "notification_reason": "unchanged",
            "automatic_writes": False,
        }

    def test_refresh_is_armed_every_sixty_seconds(self):
        runtime = ClientLiveConflictRefreshRuntime(
            _Window(_Natural(self.duplicate()))
        )
        runtime.arm()
        runtime.arm()
        self.assertEqual(runtime.timer.interval, 60_000)
        self.assertEqual(runtime.timer.starts, 1)

    def test_new_or_changed_conflict_is_delivered(self):
        natural = _Natural(self.conflict())
        window = _Window(natural)
        runtime = ClientLiveConflictRefreshRuntime(window)

        runtime.run()

        self.assertEqual(natural.calls, 1)
        self.assertEqual(len(window.events), 1)
        self.assertEqual(window.events[0]["state"], "important")
        self.assertFalse(window.events[0]["requires_confirmation"])

    def test_identical_conflict_is_not_repeated(self):
        natural = _Natural(self.duplicate())
        window = _Window(natural)

        ClientLiveConflictRefreshRuntime(window).run()

        self.assertEqual(natural.calls, 1)
        self.assertEqual(window.events, [])

    def test_busy_or_pending_confirmation_is_not_interrupted(self):
        natural = _Natural(self.conflict())
        window = _Window(natural)
        runtime = ClientLiveConflictRefreshRuntime(window)

        window.presenter.busy = True
        runtime.run()
        window.presenter.busy = False
        window.owner_window.pending_thought = {"confirmation": True}
        runtime.run()

        self.assertEqual(natural.calls, 0)
        self.assertEqual(window.events, [])

    def test_transient_failure_waits_for_next_timer_cycle(self):
        class BrokenNatural:
            calls = 0

            def startup_conflict_scan(self):
                self.calls += 1
                raise RuntimeError("temporary")

        natural = BrokenNatural()
        window = _Window(natural)
        runtime = ClientLiveConflictRefreshRuntime(window)

        runtime.run()

        self.assertEqual(natural.calls, 1)
        self.assertFalse(runtime.running)
        self.assertEqual(window.events, [])

    def test_mixin_and_stage_are_wired(self):
        root = Path(__file__).resolve().parents[1]
        mixin = (root / "app/gui/client_online_mixin.py").read_text(
            encoding="utf-8"
        )
        service = (root / "app/natural_actions/service.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ClientLiveConflictRefreshRuntime", mixin)
        self.assertIn("_live_conflict_refresh_runtime().arm()", mixin)
        self.assertIn('"B178": "LIVE_CONFLICT_REFRESH_READY"', service)

    def test_refresh_is_read_only_and_bounded(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "app/gui/client_live_conflict_refresh.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "create_event(",
            "update_event(",
            "delete_event(",
            "move_event(",
            "say_safe(",
        ):
            self.assertNotIn(marker, source)
        self.assertLess(len(source.splitlines()), 100)


if __name__ == "__main__":
    unittest.main()

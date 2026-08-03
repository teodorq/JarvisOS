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

from app.gui.client_safe_proactivity import ClientSafeProactivityRuntime


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

    def setInterval(self, milliseconds: int) -> None:
        self.interval = milliseconds

    def isActive(self) -> bool:
        return self.active

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def fire(self) -> None:
        self.timeout.callback()


class _Visible:
    def __init__(self, visible=False) -> None:
        self.visible = visible

    def isVisible(self) -> bool:
        return self.visible


class _Entry:
    def __init__(self, value="") -> None:
        self.value = value

    def text(self) -> str:
        return self.value


class _Window:
    def __init__(self) -> None:
        self.presenter = SimpleNamespace(busy=False)
        self.owner_window = SimpleNamespace(pending_thought=None)
        self.confirm_frame = _Visible(False)
        self.command_entry = _Entry("")
        self.events = []

    def _on_client_event(self, event) -> None:
        self.events.append(dict(event))


class B179SafeProactivityPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = patch(
            "app.gui.client_safe_proactivity.QTimer",
            _Timer,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    @staticmethod
    def event(message="Nowy konflikt w kalendarzu."):
        return {
            "state": "important",
            "message": message,
            "progress": 50,
            "requires_confirmation": True,
        }

    def test_idle_alert_is_delivered_without_voice_or_confirmation(self):
        window = _Window()
        runtime = ClientSafeProactivityRuntime(window)

        delivered = runtime.deliver(self.event(), priority=30)

        self.assertTrue(delivered)
        self.assertEqual(len(window.events), 1)
        self.assertFalse(window.events[0]["requires_confirmation"])
        self.assertEqual(window.events[0]["progress"], 0)

    def test_busy_alert_waits_and_is_flushed_when_ready(self):
        window = _Window()
        window.presenter.busy = True
        runtime = ClientSafeProactivityRuntime(window)

        runtime.deliver(self.event(), priority=30)
        self.assertEqual(window.events, [])
        self.assertEqual(runtime.status()["pending_count"], 1)

        window.presenter.busy = False
        runtime.timer.fire()
        self.assertEqual(len(window.events), 1)
        self.assertEqual(runtime.status()["pending_count"], 0)

    def test_confirmation_and_user_typing_are_not_interrupted(self):
        window = _Window()
        runtime = ClientSafeProactivityRuntime(window)
        window.owner_window.pending_thought = {"confirmation": True}
        runtime.deliver(self.event("Pierwszy"), priority=30)
        runtime.timer.fire()
        self.assertEqual(window.events, [])

        window.owner_window.pending_thought = None
        window.command_entry.value = "Piszę wiadomość"
        runtime.timer.fire()
        self.assertEqual(window.events, [])

        window.command_entry.value = ""
        runtime.timer.fire()
        self.assertEqual(window.events[0]["message"], "Pierwszy")

    def test_only_one_pending_alert_and_higher_priority_wins(self):
        window = _Window()
        window.presenter.busy = True
        runtime = ClientSafeProactivityRuntime(window)

        runtime.deliver(self.event("Konflikt"), priority=30, kind="conflict")
        runtime.deliver(self.event("Brief"), priority=10, kind="brief")
        self.assertEqual(runtime.status()["pending_kind"], "conflict")

        runtime.deliver(self.event("Nowszy konflikt"), priority=30, kind="conflict")
        window.presenter.busy = False
        runtime.timer.fire()
        self.assertEqual(len(window.events), 1)
        self.assertEqual(window.events[0]["message"], "Nowszy konflikt")

    def test_client_message_hides_technical_details(self):
        window = _Window()
        runtime = ClientSafeProactivityRuntime(window)

        runtime.deliver(
            self.event("Traceback C:\\JarvisAI\\app\\file.py:12"),
            priority=30,
        )

        message = window.events[0]["message"]
        self.assertNotIn("Traceback", message)
        self.assertNotIn("C:\\", message)

    def test_runtime_hooks_use_safe_queue(self):
        root = Path(__file__).resolve().parents[1]
        mixin = (root / "app/gui/client_online_mixin.py").read_text(
            encoding="utf-8"
        )
        live = (root / "app/gui/client_live_conflict_refresh.py").read_text(
            encoding="utf-8"
        )
        startup = (
            root / "app/gui/client_startup_conflict_runtime.py"
        ).read_text(encoding="utf-8")
        service = (root / "app/natural_actions/service.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("ClientSafeProactivityRuntime", mixin)
        self.assertIn("_safe_proactivity_runtime().deliver", mixin)
        self.assertIn("runtime.request(", live)
        self.assertIn("runtime.deliver(", live)
        self.assertIn("runtime.request(", startup)
        self.assertIn('"B179": "SAFE_PROACTIVITY_POLICY_READY"', service)

    def test_policy_is_read_only_bounded_and_non_voice(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "app/gui/client_safe_proactivity.py"
        source = path.read_text(encoding="utf-8")

        for marker in (
            "create_event(",
            "update_event(",
            "delete_event(",
            "move_event(",
            "say_safe(",
        ):
            self.assertNotIn(marker, source)
        self.assertLess(len(source.splitlines()), 140)


if __name__ == "__main__":
    unittest.main()

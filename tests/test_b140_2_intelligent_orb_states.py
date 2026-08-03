from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.jarvis_experience.smart_task_loop import SmartTaskLoop

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.client_experience.controller import ClientExperienceController
    from app.gui.client_experience_window import ClientExperienceWindow
    from app.gui.halo_widget import HaloWidget
    HAS_QT = True
except Exception:
    QApplication = None
    ClientExperienceController = None
    ClientExperienceWindow = None
    HaloWidget = None
    HAS_QT = False


class FakeBrain:
    def __init__(self) -> None:
        self.executions = 0

    def think(self, _command: str) -> dict:
        return {
            "can_execute": True,
            "actions": [{"action_type": "OPEN_APP"}],
        }

    def execute(self, _thought: dict) -> str:
        self.executions += 1
        return "Zadanie wykonane."


class Owner:
    pending_thought = None

    def say_safe(self, _text): return None
    def show(self): return None
    def hide(self): return None
    def raise_(self): return None
    def activateWindow(self): return None
    def close(self): return None
    def process_client_command(self, _text): return None


class TestB1402IntelligentOrbStates(unittest.TestCase):
    def test_plan_and_execute_are_separate(self) -> None:
        brain = FakeBrain()
        loop = SmartTaskLoop(
            brain,
            lambda _command, _read_only: {"allowed": True},
            lambda _thought: True,
        )
        plan = loop.plan("otwórz kalendarz")
        self.assertEqual(plan.status, "READY")
        self.assertEqual(brain.executions, 0)
        result = loop.execute(plan.thought or {})
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(brain.executions, 1)

    def test_prepare_remains_backward_compatible(self) -> None:
        brain = FakeBrain()
        loop = SmartTaskLoop(
            brain,
            lambda _command, _read_only: {"allowed": True},
            lambda _thought: True,
        )
        result = loop.prepare("otwórz kalendarz")
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(brain.executions, 1)

    @unittest.skipUnless(HAS_QT, "PySide6 is unavailable")
    def test_halo_supports_all_public_states_and_progress(self) -> None:
        app = QApplication.instance() or QApplication([])
        del app
        halo = HaloWidget()
        for state in (
            "idle",
            "listening",
            "thinking",
            "acting",
            "success",
            "warning",
            "error",
        ):
            halo.set_state(state, 64)
            self.assertEqual(halo.state, state)
            self.assertEqual(halo.progress, 64)
        self.assertTrue(halo.animation_running)
        halo.deleteLater()

    @unittest.skipUnless(HAS_QT, "PySide6 is unavailable")
    def test_presenter_drives_client_state_without_owner_details(self) -> None:
        app = QApplication.instance() or QApplication([])
        del app
        with TemporaryDirectory() as temporary:
            window = ClientExperienceWindow(
                ClientExperienceController(temporary),
                Owner(),
            )
            window.presenter.apply_event({
                "state": "acting",
                "message": "Wykonuję zadanie.",
                "progress": 61,
                "traceback": "secret",
                "path": r"C:\\JarvisAI\\app",
            })
            self.assertEqual(window.presenter.state, "acting")
            self.assertEqual(window.state_label.text(), "DZIAŁAM")
            self.assertEqual(window.halo.progress, 61)
            self.assertNotIn("JarvisAI", window.message_label.text())
            window._sync_timer.stop()
            window.deleteLater()

    def test_source_limits_and_runtime_sequence_hold(self) -> None:
        root = Path(__file__).resolve().parents[1]
        client = (root / "app/gui/client_experience_window.py").read_text(
            encoding="utf-8"
        )
        runtime = (root / "app/gui/client_command_runtime.py").read_text(
            encoding="utf-8"
        )
        presenter = (root / "app/gui/client_state_presenter.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(client.splitlines()), 440)
        self.assertIn("ClientStatePresenter", client)
        self.assertIn("QTimer.singleShot", runtime)
        self.assertIn('_publish_client_event(\n            state="acting"', runtime)
        self.assertIn("ClientIsolationPolicy.sanitize_event", presenter)


if __name__ == "__main__":
    unittest.main()

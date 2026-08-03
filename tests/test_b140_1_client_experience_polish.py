from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.jarvis_experience.owner_access import OwnerAccessGate

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel
    from app.client_experience.controller import ClientExperienceController
    from app.gui.client_experience_window import ClientExperienceWindow
    HAS_QT = True
except Exception:
    QApplication = None
    QLabel = None
    ClientExperienceController = None
    ClientExperienceWindow = None
    HAS_QT = False


class TestB1401ClientExperiencePolish(unittest.TestCase):
    def test_owner_pin_is_hashed_and_verifies(self) -> None:
        with TemporaryDirectory() as temporary:
            gate = OwnerAccessGate(temporary)
            gate.set_pin("2468")
            state_path = Path(temporary) / "data" / "client_experience" / "owner_access.json"
            content = state_path.read_text(encoding="utf-8")
            self.assertNotIn("2468", content)
            self.assertTrue(gate.verify("2468")[0])
            self.assertFalse(gate.verify("1357")[0])

    def test_pin_validation_rejects_weak_format(self) -> None:
        with TemporaryDirectory() as temporary:
            gate = OwnerAccessGate(temporary)
            with self.assertRaises(ValueError):
                gate.set_pin("12ab")

    @unittest.skipUnless(HAS_QT, "PySide6 is unavailable")
    def test_client_has_no_visible_owner_switch_or_release_labels(self) -> None:
        app = QApplication.instance() or QApplication([])
        del app
        with TemporaryDirectory() as temporary:
            class Owner:
                pending_thought = None
                def say_safe(self, _text): return None
                def show(self): return None
                def hide(self): return None
                def raise_(self): return None
                def activateWindow(self): return None
                def close(self): return None

            window = ClientExperienceWindow(
                ClientExperienceController(temporary), Owner()
            )
            labels = " ".join(
                widget.text() for widget in window.findChildren(QLabel)
                if widget.isVisibleTo(window)
            )
            self.assertTrue(window.owner_button.isHidden())
            self.assertEqual(window.stable_label.text(), "JARVIS ONLINE")
            self.assertNotIn("STABLE RC", labels)
            self.assertNotIn("BETA", labels)
            self.assertNotIn("TRYB WŁAŚCICIELA", labels)
            window._sync_timer.stop()
            window.deleteLater()

    def test_client_opens_maximized_and_source_limits_hold(self) -> None:
        root = Path(__file__).resolve().parents[1]
        main = (root / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        client = (root / "app" / "gui" / "client_experience_window.py").read_text(encoding="utf-8")
        self.assertIn("client_window.showMaximized()", main)
        self.assertIn('QKeySequence("Ctrl+Shift+F12")', client)
        self.assertLess(len(main.splitlines()), 440)
        self.assertLess(len(client.splitlines()), 440)


if __name__ == "__main__":
    unittest.main()

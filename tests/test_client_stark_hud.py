from __future__ import annotations

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.gui.client_hud_panels import build_client_hud_row


class _HudWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.owner_window = SimpleNamespace(voice_online=True)
        self.experience_v2 = SimpleNamespace(toggle_tools=lambda: None)


class ClientStarkHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_corner_hud_exposes_status_menu_settings_and_chat_mount(self) -> None:
        window = _HudWindow()
        layout = build_client_hud_row(window, QLabel("CORE"))
        self.assertIsNotNone(layout)
        self.assertEqual(window.tools_button.text(), "NARZĘDZIA")
        self.assertEqual(window.settings_button.text(), "USTAWIENIA")
        self.assertEqual(window.exit_button.text(), "WYJDŹ")
        self.assertIsNotNone(window.conversation_host_layout)
        self.assertIn("po wydaniu polecenia", window.conversation_placeholder.text())
        window.close()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.gui.client_hud_panels import build_client_hud_row
from app.gui.cinematic_entity_widget import CinematicEntityWidget


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
        self.assertIsNotNone(window.status_host_layout)
        self.assertIn("po wydaniu polecenia", window.conversation_placeholder.text())
        window.close()

    def test_main_entity_keeps_the_public_halo_state_contract(self) -> None:
        entity = CinematicEntityWidget()
        entity.set_state("acting", 42)
        self.assertEqual(entity.state, "acting")
        self.assertEqual(entity.progress, 42)
        entity.close()


if __name__ == "__main__":
    unittest.main()

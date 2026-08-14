from __future__ import annotations

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.client_hud_panels import build_client_hud_row


class _HudWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.owner_window = SimpleNamespace(voice_online=True)
        self.tools_hidden = False
        self.experience_v2 = SimpleNamespace(
            toggle_tools=lambda: None,
            tools=SimpleNamespace(hide_tools=self._hide_tools),
        )
        self.owner_unlocks: list[bool] = []
        self.owner_access = SimpleNamespace(
            request_unlock=lambda: self.owner_unlocks.append(True)
        )
        self.stack = QStackedWidget(self)
        self.client_page = QWidget()
        self.setup_page = QWidget()
        setup = QVBoxLayout(self.setup_page)
        title = QLabel("PIERWSZE URUCHOMIENIE")
        title.setObjectName("ClientState")
        subtitle = QLabel("Ustaw podstawy")
        subtitle.setObjectName("ClientMessage")
        self.name_entry = QLineEdit()
        start = QPushButton("ZAPISZ")
        start.setObjectName("ClientPrimary")
        self.setup_feedback = QLabel("stare")
        for widget in (title, subtitle, self.name_entry, start, self.setup_feedback):
            setup.addWidget(widget)
        self.stack.addWidget(self.client_page)
        self.stack.addWidget(self.setup_page)
        self.stack.setCurrentWidget(self.client_page)

    def _hide_tools(self) -> None:
        self.tools_hidden = True


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
        self.assertFalse(hasattr(window, "presence_halo"))
        self.assertIn("po wydaniu polecenia", window.conversation_placeholder.text())
        window.settings_button.click()
        self.assertIs(window.stack.currentWidget(), window.setup_page)
        self.assertTrue(window.tools_hidden)
        self.assertEqual(window.owner_unlocks, [])
        self.assertEqual(
            window.setup_page.findChild(QLabel, "ClientState").text(),
            "USTAWIENIA JARVIS OS",
        )
        self.assertEqual(window.client_settings_back.text(), "WRÓĆ")
        window.close()

if __name__ == "__main__":
    unittest.main()

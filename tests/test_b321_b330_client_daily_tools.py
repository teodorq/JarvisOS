from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.gui.client_tool_drawer import ClientToolDrawer, SAFE_CLIENT_ACTIONS


class _Window(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.message_label = QLabel("Gotowy")
        self.activity_label = QLabel("Gotowy do działania")
        self.command_entry = QLineEdit()
        self.tools_button = QPushButton("WIĘCEJ")
        self.submitted: list[str] = []
        layout.addWidget(self.message_label)
        layout.addWidget(self.activity_label)
        layout.addWidget(self.command_entry)

    def _submit_text(self, text: str) -> None:
        self.submitted.append(text)


class TestB321B330ClientDailyTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_manifest_closes_all_ten_stages(self) -> None:
        manifest = json.loads(
            Path("config/b321_b330_client_daily_tools.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            list(manifest["stages"]),
            [f"B{number}" for number in range(321, 331)],
        )
        self.assertTrue(all(
            value.endswith("READY") for value in manifest["stages"].values()
        ))
        self.assertTrue(manifest["safety"]["writes_require_confirmation"])
        self.assertTrue(manifest["safety"]["owner_gate_unchanged"])

    def test_catalog_contains_only_client_safe_commands(self) -> None:
        actions = [action for _group, items in SAFE_CLIENT_ACTIONS for action in items]
        self.assertGreaterEqual(len(actions), 12)
        self.assertTrue(any(action.guided for action in actions))
        for action in actions:
            with self.subTest(action=action.label):
                self.assertEqual(
                    ClientCapabilityPolicy.denial_message(action.command),
                    "",
                )

    def test_direct_action_runs_and_closes_drawer(self) -> None:
        window = _Window()
        drawer = ClientToolDrawer(window)
        window.show()
        drawer.show()
        action = SAFE_CLIENT_ACTIONS[0][1][0]
        drawer.run(action)
        self.assertEqual(window.submitted, [action.command])
        self.assertFalse(drawer.isVisible())
        self.assertEqual(window.tools_button.text(), "WIĘCEJ")
        window.close()

    def test_guided_action_prepares_natural_command_without_running_it(self) -> None:
        window = _Window()
        drawer = ClientToolDrawer(window)
        action = next(
            action
            for _group, items in SAFE_CLIENT_ACTIONS
            for action in items
            if action.guided
        )
        drawer.run(action)
        self.assertEqual(window.command_entry.text(), action.command)
        self.assertEqual(window.message_label.text(), action.hint)
        self.assertEqual(window.submitted, [])
        window.close()

    def test_hud_integration_and_theme_stay_compact(self) -> None:
        root = Path(__file__).resolve().parents[1]
        hud = (root / "app/gui/client_hud_panels.py").read_text(encoding="utf-8")
        v2 = (root / "app/gui/client_experience_v2.py").read_text(encoding="utf-8")
        theme = (root / "app/gui/client_theme.py").read_text(encoding="utf-8")
        self.assertIn("show_tools=True", hud)
        self.assertIn("ClientToolDrawer", v2)
        self.assertIn("ClientToolsPanel", theme)
        self.assertLess(len(theme.splitlines()), 120)


if __name__ == "__main__":
    unittest.main()

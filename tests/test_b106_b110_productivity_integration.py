from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from app.gui.productivity_center_page import ProductivityCenterPage
    HAS_PYSIDE6 = True
except ModuleNotFoundError:
    QApplication = None
    ProductivityCenterPage = None
    HAS_PYSIDE6 = False

from app.ai.brain_command_router import BrainCommandRouter
from app.assistant.controller import PersonalAssistantController
from app.gui.command_safety import is_safe_read_only_thought
from app.productivity.controller import ProductivitySuiteController


class B106B110ProductivityIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (QApplication.instance() or QApplication([])) if HAS_PYSIDE6 else None

    def test_status_routes_as_read_only(self) -> None:
        with TemporaryDirectory() as temporary:
            brain = MagicMock()
            brain.project_root = temporary
            brain.memory = MagicMock()
            brain.cognitive = MagicMock()
            brain.personal_assistant_controller = PersonalAssistantController(temporary)
            thought = BrainCommandRouter().think(brain, "Pokaż status B106-B110")
            self.assertEqual(thought["handler"], "personal_assistant")
            self.assertTrue(is_safe_read_only_thought(thought))

    def test_mail_export_requires_confirmation_path(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan("Eksportuj szkic email")
            self.assertFalse(is_safe_read_only_thought(thought))

    def test_demo_commands_update_all_services(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = ProductivitySuiteController(temporary)
            self.assertIn("utworzono szkic", controller.handle("Utwórz szkic email demo"))
            self.assertIn("zapisano spotkanie", controller.handle("Dodaj spotkanie demo"))
            self.assertIn("utworzono", controller.handle("Utwórz dokument demo"))
            self.assertIn("dodano przypomnienie", controller.handle("Dodaj przypomnienie B109 demo"))
            status = controller.status()
            self.assertEqual(status["status"], "DAILY_PRODUCTIVITY_SUITE_READY")
            self.assertFalse(status["safety"]["remote_mail_delivery"])

    @unittest.skipUnless(HAS_PYSIDE6, "PySide6 is unavailable")
    def test_gui_refreshes_without_side_effects(self) -> None:
        with TemporaryDirectory() as temporary:
            page = ProductivityCenterPage(ProductivitySuiteController(temporary))
            page.refresh()
            self.assertEqual(page.overall.full_text, "PRODUKTYWNOŚĆ GOTOWA")
            page.deleteLater()

    def test_new_modules_stay_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/productivity/common.py": 120,
            "app/productivity/mail_center.py": 240,
            "app/productivity/calendar_center.py": 220,
            "app/productivity/document_center.py": 260,
            "app/productivity/reminder_center.py": 220,
            "app/productivity/daily_briefing.py": 220,
            "app/productivity/controller.py": 340,
            "app/gui/productivity_center_page.py": 360,
            "app/assistant/controller.py": 480,
            "app/gui/main_window.py": 440,
        }
        for relative, limit in limits.items():
            with self.subTest(relative=relative):
                self.assertLess(len((root / relative).read_text(encoding="utf-8").splitlines()), limit)


if __name__ == "__main__":
    unittest.main()

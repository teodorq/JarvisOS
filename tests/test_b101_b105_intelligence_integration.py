from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from app.gui.intelligence_center_page import IntelligenceCenterPage
    HAS_PYSIDE6 = True
except ModuleNotFoundError:
    QApplication = None
    IntelligenceCenterPage = None
    HAS_PYSIDE6 = False

from app.ai.brain_command_router import BrainCommandRouter
from app.assistant.controller import PersonalAssistantController
from app.gui.command_safety import is_safe_read_only_thought
from app.intelligence.controller import IntelligenceSuiteController


class B101B105IntelligenceIntegrationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (QApplication.instance() or QApplication([])) if HAS_PYSIDE6 else None

    def test_status_routes_through_personal_assistant_read_only(self) -> None:
        with TemporaryDirectory() as temporary:
            brain = MagicMock()
            brain.project_root = temporary
            brain.memory = MagicMock()
            brain.cognitive = MagicMock()
            brain.personal_assistant_controller = PersonalAssistantController(temporary)
            thought = BrainCommandRouter().think(brain, "Pokaż status B101-B105")
            self.assertEqual(thought["handler"], "personal_assistant")
            self.assertTrue(is_safe_read_only_thought(thought))

    def test_mutating_memory_command_requires_normal_confirmation(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan(
                "Zapamiętaj w pamięci 2.0: Używaj pełnych plików"
            )
            self.assertFalse(is_safe_read_only_thought(thought))

    def test_controller_demo_flow_updates_memory_and_autonomy(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = IntelligenceSuiteController(temporary)
            self.assertIn("zapisano pamięć", controller.handle(
                "Zapamiętaj w pamięci 2.0: pełne pliki ZIP"
            ))
            self.assertIn("utworzono", controller.handle(
                "Utwórz zadanie autonomii 2.0: Demo | Pierwszy; Drugi"
            ))
            self.assertIn("uruchomiono", controller.handle(
                "Uruchom zadanie autonomii 2.0"
            ))
            self.assertIn("postęp 1/2", controller.handle(
                "Następny etap autonomii 2.0"
            ))

    @unittest.skipUnless(HAS_PYSIDE6, "PySide6 is unavailable")
    def test_gui_refreshes_without_side_effects(self) -> None:
        with TemporaryDirectory() as temporary:
            page = IntelligenceCenterPage(IntelligenceSuiteController(temporary))
            page.refresh()
            self.assertEqual(page.overall.full_text, "INTELIGENCJA GOTOWA")
            page.deleteLater()

    def test_new_modules_and_main_window_stay_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/intelligence/vision_runtime.py": 280,
            "app/intelligence/brain_context.py": 220,
            "app/intelligence/desktop_orchestrator.py": 220,
            "app/intelligence/memory_index.py": 220,
            "app/intelligence/autonomy_center.py": 280,
            "app/intelligence/controller.py": 300,
            "app/gui/intelligence_center_page.py": 320,
            "app/gui/main_window.py": 440,
            "app/assistant/controller.py": 480,
        }
        for relative, limit in limits.items():
            with self.subTest(relative=relative):
                self.assertLess(
                    len((root / relative).read_text(encoding="utf-8").splitlines()),
                    limit,
                )


if __name__ == "__main__":
    unittest.main()

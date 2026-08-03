from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from app.gui.assistant_productivity_page import AssistantProductivityPage
    HAS_PYSIDE6 = True
except ModuleNotFoundError:
    QApplication = None
    AssistantProductivityPage = None
    HAS_PYSIDE6 = False

from app.ai.brain_command_router import BrainCommandRouter
from app.assistant.controller import PersonalAssistantController
from app.gui.command_safety import is_safe_read_only_thought


class B96B100RoutingGuiTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (QApplication.instance() or QApplication([])) if HAS_PYSIDE6 else None

    def test_brain_router_prioritizes_assistant_status(self) -> None:
        with TemporaryDirectory() as temporary:
            brain = MagicMock()
            brain.project_root = temporary
            brain.memory = MagicMock()
            brain.cognitive = MagicMock()
            brain.personal_assistant_controller = PersonalAssistantController(
                temporary,
                memory=brain.memory,
            )
            thought = BrainCommandRouter().think(
                brain,
                "Jarvis proszę pokaż status asystenta",
            )
            self.assertEqual(thought["handler"], "personal_assistant")
            self.assertTrue(is_safe_read_only_thought(thought))
            brain.cognitive.after_plan.assert_called_once()

    def test_mutating_assistant_command_is_not_read_only(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan(
                "Utwórz zadanie wieloetapowe Demo: krok 1; krok 2"
            )
            self.assertFalse(is_safe_read_only_thought(thought))

    @unittest.skipUnless(HAS_PYSIDE6, "PySide6 is unavailable in this environment")
    def test_productivity_page_refreshes_without_runtime_side_effects(self) -> None:
        with TemporaryDirectory() as temporary:
            page = AssistantProductivityPage(
                PersonalAssistantController(temporary)
            )
            page.refresh()
            self.assertEqual(page.overall.full_text, "ASYSTENT GOTOWY")
            page.deleteLater()

    def test_main_window_stays_below_audit_limit(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/gui/main_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn("AssistantProductivityPage", source)
        self.assertIn("ASYSTENT I CODZIENNA PRACA", source)
        self.assertLess(len(source.splitlines()), 440)

    def test_new_modules_stay_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/assistant/natural_language.py": 300,
            "app/assistant/reliable_desktop.py": 320,
            "app/assistant/project_memory.py": 320,
            "app/assistant/voice_runtime.py": 260,
            "app/assistant/daily_work.py": 420,
            "app/assistant/controller.py": 480,
            "app/gui/assistant_productivity_page.py": 360,
            "app/voice/voice_listener.py": 220,
        }
        for relative, limit in limits.items():
            with self.subTest(relative=relative):
                lines = (root / relative).read_text(encoding="utf-8").splitlines()
                self.assertLess(len(lines), limit)


if __name__ == "__main__":
    unittest.main()

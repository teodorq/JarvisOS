from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from app.gui.stability_beta_page import StabilityBetaPage
    HAS_PYSIDE6 = True
except ModuleNotFoundError:
    QApplication = None
    StabilityBetaPage = None
    HAS_PYSIDE6 = False

from app.ai.brain_command_router import BrainCommandRouter
from app.assistant.controller import PersonalAssistantController
from app.gui.command_safety import is_safe_read_only_thought
from app.stability.controller import StabilitySuiteController


class B111B115StabilityIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (QApplication.instance() or QApplication([])) if HAS_PYSIDE6 else None

    @staticmethod
    def make_project(path: str) -> Path:
        root = Path(path)
        for relative in ("main.py", "app/ai/brain.py", "app/gui/main_window.py", "app/assistant/controller.py"):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# demo\n", encoding="utf-8")
        (root / "tests").mkdir(exist_ok=True)
        (root / "config").mkdir(exist_ok=True)
        (root / "config/business_integrity_manifest.json").write_text(
            json.dumps({"files": {"main.py": "abc"}}), encoding="utf-8"
        )
        return root

    def test_status_routes_as_read_only(self) -> None:
        with TemporaryDirectory() as temporary:
            brain = MagicMock()
            brain.project_root = temporary
            brain.memory = MagicMock()
            brain.cognitive = MagicMock()
            brain.personal_assistant_controller = PersonalAssistantController(temporary)
            thought = BrainCommandRouter().think(brain, "Pokaż status B111-B115")
            self.assertEqual(thought["handler"], "personal_assistant")
            self.assertTrue(is_safe_read_only_thought(thought))

    def test_full_manual_sequence_unlocks_beta(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.make_project(temporary)
            runtime = lambda: {
                "conversation": {"status": "READY"},
                "intelligence": {"status": "READY"},
                "productivity": {"status": "READY"},
                "safety": {"auto_approve": False, "remote_code_execution": False},
            }
            controller = StabilitySuiteController(root, runtime_status=runtime)
            self.assertIn("PASSED", controller.handle("Uruchom testy realnych scenariuszy B111"))
            self.assertIn("wynik", controller.handle("Uruchom test wydajności B112"))
            controller.handle("Symuluj zawieszenie usługi B113")
            self.assertIn("RECOVERED", controller.handle("Odzyskaj usługę B113"))
            controller.handle("Przygotuj restart usługi B114")
            self.assertIn("stan przywrócony TAK", controller.handle("Wykonaj restart usługi B114"))
            self.assertIn("PASSED", controller.handle("Uruchom audyt Business Beta B115"))
            self.assertIn("BUSINESS_BETA_READY", controller.handle("Potwierdź Business Beta B115"))

    def test_beta_confirmation_requires_normal_confirmation_gate(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan("Potwierdź Business Beta B115")
            self.assertFalse(is_safe_read_only_thought(thought))

    @unittest.skipUnless(HAS_PYSIDE6, "PySide6 is unavailable")
    def test_gui_refreshes_without_side_effects(self) -> None:
        with TemporaryDirectory() as temporary:
            page = StabilityBetaPage(StabilitySuiteController(temporary))
            page.refresh()
            self.assertEqual(page.overall.full_text, "STABILNOŚĆ GOTOWA")
            page.deleteLater()

    def test_new_modules_stay_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/stability/common.py": 100,
            "app/stability/scenario_validator.py": 190,
            "app/stability/performance_center.py": 190,
            "app/stability/recovery_center.py": 220,
            "app/stability/service_restart.py": 190,
            "app/stability/beta_readiness.py": 180,
            "app/stability/controller.py": 310,
            "app/gui/stability_beta_page.py": 300,
            "app/assistant/controller.py": 480,
            "app/gui/main_window.py": 440,
        }
        for relative, limit in limits.items():
            with self.subTest(relative=relative):
                self.assertLess(len((root / relative).read_text(encoding="utf-8").splitlines()), limit)


if __name__ == "__main__":
    unittest.main()

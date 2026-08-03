from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.business.business_config import BusinessConfigStore
from app.client_experience.controller import ClientExperienceController

try:
    from PySide6.QtWidgets import QApplication
    from app.gui.client_experience_window import ClientExperienceWindow
    from app.gui.halo_widget import HaloWidget
    HAS_PYSIDE6 = True
except ModuleNotFoundError:
    QApplication = None
    ClientExperienceWindow = None
    HaloWidget = None
    HAS_PYSIDE6 = False


class B116B120ClientExperienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = (QApplication.instance() or QApplication([])) if HAS_PYSIDE6 else None

    @staticmethod
    def prepare_root(path: str) -> Path:
        root = Path(path)
        (root / "config").mkdir(parents=True, exist_ok=True)
        BusinessConfigStore(root).ensure()
        beta = root / "data" / "stability" / "business_beta.json"
        beta.parent.mkdir(parents=True, exist_ok=True)
        beta.write_text(json.dumps({
            "audits": [{"audit_id": "audit", "status": "PASSED", "passed": 5, "total": 5}],
            "confirmations": [{"status": "BUSINESS_BETA_READY", "audit_id": "audit"}],
        }), encoding="utf-8")
        return root

    def test_first_run_profile_is_local_and_safe(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.prepare_root(temporary)
            controller = ClientExperienceController(root)
            profile = controller.configure(
                display_name="Kacper <script>",
                voice_enabled=True,
                interaction_mode="VOICE_AND_TEXT",
            )
            self.assertTrue(profile["setup_completed"])
            self.assertNotIn("<", profile["display_name"])
            self.assertTrue(controller.should_start_client())
            safety = BusinessConfigStore(root).ensure()["safety"]
            self.assertFalse(safety["auto_approve"])
            self.assertTrue(safety["require_confirmation"])
            self.assertEqual(safety["max_active_executions"], 1)
            self.assertFalse(safety["allow_remote_code_execution"])

    def test_halo_state_is_bounded(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = ClientExperienceController(self.prepare_root(temporary))
            self.assertEqual(controller.set_halo("thinking", "Analiza")["state"], "thinking")
            self.assertEqual(controller.set_halo("unknown", "Test")["state"], "idle")
            self.assertEqual(len(controller.HALO_STATES), 7)

    def test_usability_gates_unlock_business_1_1_stable(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.prepare_root(temporary)
            controller = ClientExperienceController(root)
            controller.configure(
                display_name="Kacper",
                voice_enabled=True,
                interaction_mode="VOICE_AND_TEXT",
            )
            audit = controller.run_usability_audit(
                width=1260,
                height=820,
                animation_running=True,
                owner_switch_available=True,
                command_input_available=True,
            )
            self.assertEqual(audit["status"], "PASSED")
            self.assertEqual(audit["passed"], 8)
            confirmation = controller.confirm_stable()
            self.assertEqual(confirmation["status"], "BUSINESS_1_1_STABLE_READY")
            self.assertFalse(confirmation["automatic_publication"])
            self.assertTrue(confirmation["owner_mode_preserved"])
            self.assertTrue((root / "AI_PLIKI/reports/JARVIS_BUSINESS_1_1_STABLE.json").is_file())

    def test_stable_is_blocked_without_beta_or_audit(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            BusinessConfigStore(root).ensure()
            controller = ClientExperienceController(root)
            controller.configure(
                display_name="Kacper",
                voice_enabled=False,
                interaction_mode="TEXT_ONLY",
            )
            audit = controller.run_usability_audit(
                width=900,
                height=600,
                animation_running=True,
                owner_switch_available=True,
                command_input_available=True,
            )
            self.assertEqual(audit["status"], "BLOCKED")
            with self.assertRaises(ValueError):
                controller.confirm_stable()

    def test_owner_mode_remains_available(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = ClientExperienceController(self.prepare_root(temporary))
            controller.set_mode("CLIENT")
            self.assertEqual(controller.status()["runtime"]["mode"], "CLIENT")
            controller.set_mode("OWNER")
            self.assertEqual(controller.status()["runtime"]["mode"], "OWNER")

    @unittest.skipUnless(HAS_PYSIDE6, "PySide6 is unavailable")
    def test_gui_has_halo_setup_and_owner_switch(self) -> None:
        with TemporaryDirectory() as temporary:
            root = self.prepare_root(temporary)

            class Owner:
                pending_thought = None
                def process_command(self, text, source="Ty"): return None
                def say_safe(self, text): return None
                def show(self): return None
                def hide(self): return None
                def raise_(self): return None
                def activateWindow(self): return None
                def close(self): return None

            window = ClientExperienceWindow(ClientExperienceController(root), Owner())
            self.assertIsInstance(window.halo, HaloWidget)
            self.assertTrue(window.owner_button.isEnabled())
            self.assertTrue(window.command_entry.isEnabled())
            window._sync_timer.stop()
            window.deleteLater()

    def test_source_limits_and_start_mode_hook(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/client_experience/controller.py": 320,
            "app/gui/halo_widget.py": 160,
            "app/gui/client_theme.py": 120,
            "app/gui/client_experience_window.py": 440,
            "app/gui/main_window.py": 440,
        }
        for relative, limit in limits.items():
            with self.subTest(relative=relative):
                count = len((root / relative).read_text(encoding="utf-8").splitlines())
                self.assertLess(count, limit)
        main = (root / "main.py").read_text(encoding="utf-8")
        owner = (root / "app/gui/main_window.py").read_text(encoding="utf-8")
        self.assertIn("show_start_mode", main)
        self.assertIn("TRYB KLIENTA", owner)
        self.assertIn("ClientExperienceWindow", owner)


if __name__ == "__main__":
    unittest.main()

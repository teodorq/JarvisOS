from __future__ import annotations

from pathlib import Path
import unittest


class B87B88BusinessReleaseGuiTests(unittest.TestCase):

    def test_main_window_exposes_release_page(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/gui/main_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn("BusinessReleasePage", source)
        self.assertIn('"release": self.release_page', source)
        self.assertIn("WDROŻENIE I RELEASE RC1", source)

    def test_release_buttons_only_prepare_commands(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/gui/business_release_page.py"
        ).read_text(encoding="utf-8")
        self.assertIn("command_requested.emit", source)
        self.assertNotIn("export_setup_package()", source)
        self.assertNotIn("export_release_candidate()", source)

    def test_main_window_and_router_stay_below_audit_limits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/main_window.py": 440,
            "app/ai/software_engineer/software_engineer_autonomy_operations_router.py": 440,
            "app/business/installation_manager.py": 340,
            "app/business/release_candidate.py": 400,
            "app/gui/business_release_page.py": 240,
        }
        for relative, limit in limits.items():
            lines = (root / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, relative)

    def test_start_script_is_portable(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "start_jarvis.bat"
        ).read_text(encoding="utf-8")
        self.assertIn("%~dp0", source)
        self.assertNotIn("cd /d C:\\JarvisAI", source)


if __name__ == "__main__":
    unittest.main()

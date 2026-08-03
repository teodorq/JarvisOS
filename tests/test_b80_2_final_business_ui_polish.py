from __future__ import annotations

from pathlib import Path
import unittest

from app.gui.business_display import (
    display_environment,
    display_status,
    same_identity,
)


class B802DisplayLocalizationTests(unittest.TestCase):
    def test_common_runtime_states_have_polish_labels(self) -> None:
        self.assertEqual(display_status("READY"), "GOTOWY")
        self.assertEqual(display_status("STOPPED"), "ZATRZYMANE")
        self.assertEqual(display_status("OWNER_DEVELOPMENT"), "TRYB WŁAŚCICIELA")
        self.assertEqual(
            display_environment("OWNER DEVELOPMENT"),
            "ROZWÓJ WŁAŚCICIELSKI",
        )

    def test_identity_comparison_ignores_spaces_and_underscores(self) -> None:
        self.assertTrue(same_identity("OWNER DEVELOPMENT", "OWNER_DEVELOPMENT"))
        self.assertFalse(same_identity("PRODUCTION", "OWNER_DEVELOPMENT"))


class B802SourceIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.window = (self.root / "app/gui/main_window.py").read_text(
            encoding="utf-8"
        )
        self.pages = (self.root / "app/gui/business_pages.py").read_text(
            encoding="utf-8"
        )
        self.widgets = (self.root / "app/gui/business_widgets.py").read_text(
            encoding="utf-8"
        )

    def test_visible_shell_is_polish_and_duplicate_owner_badge_is_hidden(self) -> None:
        self.assertIn("NAWIGACJA BIZNESOWA", self.window)
        self.assertIn("LICENCJA I ZAUFANIE", self.window)
        self.assertIn("self.license_pill.hide()", self.window)
        self.assertIn("same_identity(label, environment)", self.window)
        self.assertIn("B80.2 FINAL UI", self.window)

    def test_long_values_have_elision_tooltips_and_console_wrap(self) -> None:
        self.assertIn("class ElidedLabel", self.widgets)
        self.assertIn("self.setToolTip(self._full_text)", self.widgets)
        self.assertIn("Qt.ElideMiddle", self.widgets)
        self.assertIn("QTextOption.WrapAnywhere", self.pages)
        self.assertIn("setMaximumBlockCount(2000)", self.pages)

    def test_environment_selector_keeps_raw_backend_values(self) -> None:
        self.assertIn(
            '("Rozwój właścicielski", "OWNER DEVELOPMENT")',
            self.pages,
        )
        self.assertIn("self.environment.currentData()", self.pages)
        self.assertIn("display_environment(environment)", self.pages)

    def test_runtime_states_are_consistently_polish(self) -> None:
        source = (self.root / "app/gui/business_command_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ANALIZA POLECENIA", source)
        self.assertIn("OCZEKIWANIE NA POTWIERDZENIE", source)
        self.assertIn("GOTOWY NA POLECENIE", source)
        self.assertNotIn('set_state("READY FOR COMMAND"', source)

    def test_ui_files_remain_below_audit_limits(self) -> None:
        limits = {
            "app/gui/main_window.py": 440,
            "app/gui/business_pages.py": 440,
            "app/gui/business_widgets.py": 220,
            "app/gui/business_display.py": 180,
            "app/gui/business_command_runtime.py": 180,
            "app/gui/business_theme.py": 260,
        }
        for relative, limit in limits.items():
            lines = (self.root / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, f"{relative}: {len(lines)} >= {limit}")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import unittest


class B84B86BusinessOperationsGuiTests(unittest.TestCase):

    def test_main_window_exposes_operations_page(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/gui/main_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn("BusinessOperationsPage", source)
        self.assertIn('"operations": self.operations_page', source)
        self.assertIn("AUDYT, BACKUPY I AKTUALIZACJE", source)

    def test_operations_buttons_only_prepare_commands(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/gui/business_operations_page.py"
        ).read_text(encoding="utf-8")
        self.assertIn("command_requested.emit", source)
        self.assertNotIn("create_business_checkpoint()", source)
        self.assertNotIn("stage_business_update()", source)

    def test_main_window_stays_below_audit_limit(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/gui/main_window.py"
        ).read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 440)


if __name__ == "__main__":
    unittest.main()

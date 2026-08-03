from __future__ import annotations

from pathlib import Path
import unittest


class B8011StartupOrderFixTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.source = (root / "app/gui/main_window.py").read_text(
            encoding="utf-8"
        )

    def test_page_context_is_created_before_workspace_build(self) -> None:
        creation = self.source.index("self.page_context = QLabel")
        workspace = self.source.index("body.addWidget(self._build_workspace(), 1)")
        self.assertLess(creation, workspace)

    def test_page_switch_is_defensive_during_startup(self) -> None:
        self.assertIn(
            'page_context = getattr(self, "page_context", None)',
            self.source,
        )
        self.assertIn("if page_context is not None:", self.source)

    def test_main_window_remains_below_audit_limit(self) -> None:
        self.assertLess(len(self.source.splitlines()), 440)


if __name__ == "__main__":
    unittest.main()

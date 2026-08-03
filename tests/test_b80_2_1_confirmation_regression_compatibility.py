from __future__ import annotations

import ast
from pathlib import Path
import unittest


class B8021ConfirmationRegressionCompatibilityTests(
    unittest.TestCase
):

    def _main_window_tree(self) -> ast.Module:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app/gui/main_window.py"
        )
        return ast.parse(
            source_path.read_text(encoding="utf-8")
        )

    def test_handle_confirmation_is_preserved(
        self,
    ) -> None:
        tree = self._main_window_tree()

        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "handle_confirmation"
        )

        self.assertGreater(
            len(method.body),
            0,
        )

    def test_confirmation_delegates_to_shared_safe_handler(
        self,
    ) -> None:
        tree = self._main_window_tree()
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "handle_confirmation"
        )

        call_names = {
            node.func.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }
        self.assertIn("handle_confirmation", call_names)

        source_path = (
            Path(__file__).resolve().parents[1]
            / "app/gui/main_window.py"
        )
        method_source = source_path.read_text(encoding="utf-8").split(
            "def handle_confirmation",
            1,
        )[1].split("def ", 1)[0]
        self.assertNotIn("self.brain.execute(pending)", method_source)

    def test_main_window_stays_below_audit_limit(
        self,
    ) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app/gui/main_window.py"
        )
        self.assertLess(
            len(source_path.read_text(encoding="utf-8").splitlines()),
            440,
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import ast
from pathlib import Path
import unittest


class B81B83BusinessPlatformGuiTests(unittest.TestCase):

    def test_main_window_exposes_platform_page(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/gui/main_window.py"
        ).read_text(encoding="utf-8")
        self.assertIn("BusinessPlatformPage", source)
        self.assertIn('"platform": self.platform_page', source)
        self.assertIn("PROFILE, LICENCJE I ROLE", source)

    def test_main_window_stays_below_limit(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/gui/main_window.py"
        ).read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 440)

    def test_runtime_calls_access_control_before_execution(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app/gui/business_command_runtime.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        process = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "process_command"
        )
        authorize_line = next(
            node.lineno for node in ast.walk(process)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "authorize"
        )
        execute_line = next(
            node.lineno for node in ast.walk(process)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_execute_thought"
        )
        self.assertLess(authorize_line, execute_line)

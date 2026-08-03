from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.ai.brain_response_formatter import (
    BrainResponseFormatter,
)


class AuditA31BrainResponsibilityTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_brain_is_reduced_below_two_thousand_lines(self) -> None:
        brain_path = self.project_root / "app/ai/brain.py"
        line_count = len(
            brain_path.read_text(
                encoding="utf-8"
            ).splitlines()
        )

        self.assertLess(
            line_count,
            2000,
        )

    def test_response_formatter_owns_large_formatting_methods(self) -> None:
        formatter_path = (
            self.project_root
            / "app/ai/brain_response_formatter.py"
        )
        tree = ast.parse(
            formatter_path.read_text(
                encoding="utf-8"
            )
        )
        formatter_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "BrainResponseFormatter"
        )
        method_names = {
            node.name
            for node in formatter_class.body
            if isinstance(node, ast.FunctionDef)
        }

        expected = {
            "_format_autonomous_dev_response",
            "_format_autonomous_status",
            "_format_meta_response",
            "_format_executive_response",
            "_format_project_director_response",
            "_format_improvement_response",
            "_format_evolution_response",
            "_format_continuous_dev_response",
            "_format_reasoning_response",
            "_format_research_response",
        }

        self.assertTrue(
            expected.issubset(method_names)
        )

    def test_brain_keeps_compatibility_wrappers(self) -> None:
        brain_path = self.project_root / "app/ai/brain.py"
        tree = ast.parse(
            brain_path.read_text(
                encoding="utf-8"
            )
        )
        brain_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "Brain"
        )
        method_names = {
            node.name
            for node in brain_class.body
            if isinstance(node, ast.FunctionDef)
        }

        self.assertIn(
            "_format_executive_response",
            method_names,
        )
        self.assertIn(
            "_format_autonomous_dev_response",
            method_names,
        )
        self.assertIn(
            "_safe_int",
            method_names,
        )

    def test_formatter_helpers_preserve_behavior(self) -> None:
        formatter = BrainResponseFormatter()

        self.assertEqual(
            formatter._safe_int("7.0"),
            7,
        )
        self.assertEqual(
            formatter._format_duration(65),
            "01:05",
        )
        self.assertIsInstance(
            formatter._format_research_response(
                {
                    "success": False,
                    "status": "FAILED",
                    "errors": ["x"],
                }
            ),
            str,
        )

    def test_formatter_is_stateless(self) -> None:
        formatter = BrainResponseFormatter()

        self.assertEqual(
            vars(formatter),
            {},
        )


if __name__ == "__main__":
    unittest.main()

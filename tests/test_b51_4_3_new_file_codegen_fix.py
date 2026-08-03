from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from app.autodev.developer_agent import DeveloperAgent


class DeveloperAgentNewFileTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp_dir.name
        )
        self.agent = DeveloperAgent.__new__(
            DeveloperAgent
        )
        self.agent.project_root = self.root

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_builds_requested_class_for_empty_file(self) -> None:
        proposal = (
            self.agent
            ._bootstrap_new_python_file(
                goal=(
                    "Utwórz nową klasę "
                    "DemoFeature"
                ),
                title=(
                    "Implementacja "
                    "funkcjonalności"
                ),
                file_path=(
                    self.root
                    / "app/demo_feature.py"
                ),
            )
        )

        self.assertIn(
            "class DemoFeature:",
            proposal,
        )
        ast.parse(proposal)

    def test_new_file_review_accepts_small_valid_class(self) -> None:
        proposal = (
            "from __future__ import annotations\n\n"
            "class DemoFeature:\n"
            "    pass\n"
        )

        review = self.agent.review_code_proposal(
            source_content="",
            proposed_content=proposal,
            file_path=(
                self.root
                / "app/demo_feature.py"
            ),
        )

        self.assertTrue(
            review["approved"]
        )
        self.assertNotIn(
            (
                "AI Code Review: propozycja usuwa "
                "zbyt dużą część istniejącego pliku."
            ),
            review["blocking_reasons"],
        )

    def test_existing_file_still_rejects_destructive_change(self) -> None:
        source = "\n".join(
            f"value_{index} = {index}"
            for index in range(20)
        )
        proposal = "value = 1\n"

        review = self.agent.review_code_proposal(
            source_content=source,
            proposed_content=proposal,
            file_path=(
                self.root
                / "app/existing.py"
            ),
        )

        self.assertFalse(
            review["approved"]
        )
        self.assertIn(
            (
                "AI Code Review: propozycja usuwa "
                "zbyt dużą część istniejącego pliku."
            ),
            review["blocking_reasons"],
        )

    def test_builds_requested_function_for_empty_file(self) -> None:
        proposal = (
            self.agent
            ._bootstrap_new_python_file(
                goal="Utwórz funkcję calculate_score",
                title="Nowa funkcjonalność",
                file_path=(
                    self.root
                    / "app/score.py"
                ),
            )
        )

        self.assertIn(
            "def calculate_score() -> None:",
            proposal,
        )
        ast.parse(proposal)

    def test_fallback_uses_filename_when_goal_is_generic(self) -> None:
        proposal = (
            self.agent
            ._bootstrap_new_python_file(
                goal="Dodaj nową funkcjonalność",
                title="Implementacja",
                file_path=(
                    self.root
                    / "app/report_engine.py"
                ),
            )
        )

        self.assertIn(
            "class ReportEngine:",
            proposal,
        )
        ast.parse(proposal)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.software_engineer.safe_development_commands import (
    plan_safe_development_command,
)
from app.gui.command_safety import is_safe_workspace_preparation_thought


EXACT_COMMAND = (
    "Przygotuj jedną bezpieczną poprawkę projektu w izolowanej kopii, "
    "pokaż diff i wyniki testów, ale niczego jeszcze nie wdrażaj."
)


class _Brain:
    def __init__(self, root: str) -> None:
        self.project_root = root
        self.cognitive = MagicMock()
        self.software_engineer_controller = MagicMock()
        self.software_engineer_controller.can_handle.return_value = True
        self.research_service = MagicMock()
        self.research_service.can_handle.return_value = True


class B2102NaturalSafePrepareRoutingTests(unittest.TestCase):
    def test_exact_practical_owner_command_routes_to_safe_prepare(self) -> None:
        with TemporaryDirectory() as directory:
            thought = plan_safe_development_command(
                _Brain(directory), EXACT_COMMAND
            )
        self.assertIsNotNone(thought)
        self.assertEqual(thought["handler"], "safe_development_prepare")
        self.assertTrue(thought["can_execute"])
        self.assertFalse(thought["requires_confirmation"])

    def test_brain_router_prioritizes_safe_prepare_before_legacy_autodev(self) -> None:
        with TemporaryDirectory() as directory:
            brain = _Brain(directory)
            thought = BrainCommandRouter().think(brain, EXACT_COMMAND)
        self.assertEqual(thought["handler"], "safe_development_prepare")
        brain.software_engineer_controller.can_handle.assert_not_called()
        brain.research_service.can_handle.assert_not_called()

    def test_exact_thought_is_allowed_as_workspace_only_operation(self) -> None:
        with TemporaryDirectory() as directory:
            thought = plan_safe_development_command(
                _Brain(directory), EXACT_COMMAND
            )
        self.assertTrue(is_safe_workspace_preparation_thought(thought))
        self.assertFalse(thought["project_write"])
        self.assertTrue(thought["workspace_only"])

    def test_natural_variant_with_diff_and_tests_is_supported(self) -> None:
        command = (
            "Stwórz zmianę w bezpiecznym workspace, pokaż różnice i testy, "
            "zostaw do decyzji bez wdrażania."
        )
        with TemporaryDirectory() as directory:
            thought = plan_safe_development_command(_Brain(directory), command)
        self.assertIsNotNone(thought)
        self.assertEqual(thought["handler"], "safe_development_prepare")

    def test_deploy_command_is_not_misclassified_as_prepare(self) -> None:
        with TemporaryDirectory() as directory:
            brain = _Brain(directory)
            brain.safe_autonomous_development_service = MagicMock()
            brain.safe_autonomous_development_service.plan_deploy.return_value = {
                "success": False,
                "message": "Brak przygotowanej poprawki.",
            }
            thought = plan_safe_development_command(
                brain, "Wdróż przygotowaną poprawkę"
            )
        self.assertEqual(thought["handler"], "safe_development_deploy")

    def test_unrelated_project_request_keeps_legacy_routing(self) -> None:
        with TemporaryDirectory() as directory:
            thought = plan_safe_development_command(
                _Brain(directory), "Przeanalizuj projekt i napisz raport."
            )
        self.assertIsNone(thought)

    def test_source_bounds_and_exact_phrase_are_present(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (
            root
            / "app/ai/software_engineer/safe_development_commands.py"
        ).read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 260)
        self.assertIn("przygotuj jedna bezpieczna poprawke", source)
        self.assertIn("_is_prepare_command", source)


if __name__ == "__main__":
    unittest.main()

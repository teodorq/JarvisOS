from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomous_cycle_commands import (
    plan_autonomous_cycle_command,
)


class B2201NaturalAutonomousCycleRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = MagicMock()

    def _plan(self, command: str):
        return plan_autonomous_cycle_command(self.brain, command)

    def test_exact_practical_owner_phrase_routes_to_cycle(self) -> None:
        thought = self._plan(
            "Uruchom jeden bezpieczny cykl autonomicznego rozwoju "
            "i zatrzymaj się przed wdrożeniem."
        )
        self.assertIsNotNone(thought)
        self.assertEqual(thought["handler"], "autonomous_cycle_run")
        self.assertTrue(thought["workspace_only"])
        self.assertFalse(thought["project_write"])

    def test_natural_phrase_without_backlog_word_is_supported(self) -> None:
        thought = self._plan(
            "Wykonaj jeden autonomiczny cykl rozwoju i zatrzymaj "
            "przed wdrożeniem"
        )
        self.assertEqual(thought["handler"], "autonomous_cycle_run")

    def test_autodev_variant_is_supported(self) -> None:
        thought = self._plan(
            "Uruchom bezpieczny cykl AutoDev bez wdrażania"
        )
        self.assertEqual(thought["handler"], "autonomous_cycle_run")

    def test_command_never_requires_confirmation_for_workspace(self) -> None:
        thought = self._plan(
            "Uruchom autonomiczny cykl rozwoju, ale nie wdrażaj"
        )
        self.assertFalse(thought["requires_confirmation"])
        self.assertFalse(thought["auto_approve"])
        self.assertFalse(thought["auto_deploy"])

    def test_deploy_command_is_not_misclassified_as_prepare(self) -> None:
        self.assertIsNone(
            self._plan("Uruchom autonomiczny cykl rozwoju i wdroż poprawkę")
        )

    def test_calendar_cycle_is_not_misclassified(self) -> None:
        self.assertIsNone(
            self._plan(
                "Uruchom cykl kalendarza i zatrzymaj się przed wdrożeniem"
            )
        )

    def test_recovery_learning_cycle_is_not_misclassified(self) -> None:
        self.assertIsNone(
            self._plan(
                "Uruchom cykl uczenia napraw i zatrzymaj się przed wdrożeniem"
            )
        )

    def test_source_contract_stays_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        relative = (
            "app/ai/software_engineer/autonomous_cycle_commands.py"
        )
        source = (root / relative).read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 220)
        self.assertNotIn("C:\\JarvisAI", source)


if __name__ == "__main__":
    unittest.main()

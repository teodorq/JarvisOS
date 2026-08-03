from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.safe_development_commands import (
    execute_safe_development_command,
    plan_safe_development_command,
)


class B2103NaturalSafeRollbackRoutingTests(unittest.TestCase):

    @staticmethod
    def _brain(*, planned: dict | None = None) -> MagicMock:
        brain = MagicMock()
        service = MagicMock()
        service.plan_rollback.return_value = planned or {
            "success": True,
            "status": "CONFIRM_ROLLBACK",
            "session": {
                "session_id": "safe-dev-rollback-1",
                "target": "app/ai/brain_response_formatter.py",
            },
            "operation_fingerprint": "rollback-fingerprint-1",
            "confirmation_message": (
                "Czy cofnąć poprawkę w "
                "app/ai/brain_response_formatter.py?"
            ),
        }
        brain.safe_autonomous_development_service = service
        return brain

    def test_exact_practical_phrase_routes_to_safe_rollback(self) -> None:
        brain = self._brain()
        thought = plan_safe_development_command(
            brain,
            "Cofnij ostatnią poprawkę projektu",
        )
        self.assertIsNotNone(thought)
        self.assertEqual(thought["handler"], "safe_development_rollback")
        self.assertTrue(thought["requires_confirmation"])
        self.assertEqual(thought["safe_session_id"], "safe-dev-rollback-1")
        self.assertEqual(
            thought["operation_fingerprint"],
            "rollback-fingerprint-1",
        )

    def test_punctuation_and_case_are_normalized(self) -> None:
        thought = plan_safe_development_command(
            self._brain(),
            "COFNIJ ostatnią poprawkę projektu!",
        )
        self.assertEqual(thought["handler"], "safe_development_rollback")

    def test_natural_project_rollback_variants_are_supported(self) -> None:
        variants = (
            "Wycofaj ostatnią poprawkę projektu",
            "Przywróć projekt sprzed ostatniej poprawki",
            "Cofnij wdrożoną poprawkę",
        )
        for command in variants:
            with self.subTest(command=command):
                thought = plan_safe_development_command(self._brain(), command)
                self.assertEqual(
                    thought["handler"],
                    "safe_development_rollback",
                )

    def test_calendar_undo_is_not_taken_by_autodev(self) -> None:
        for command in (
            "Cofnij ostatnią zmianę w kalendarzu",
            "Cofnij ostatnie spotkanie",
            "Przywróć poprzedni termin wydarzenia",
        ):
            with self.subTest(command=command):
                self.assertIsNone(
                    plan_safe_development_command(self._brain(), command)
                )

    def test_no_deployed_patch_never_creates_confirmation(self) -> None:
        brain = self._brain(
            planned={
                "success": False,
                "status": "NO_DEPLOYED_PATCH",
                "message": "Nie ma ostatniej wdrożonej poprawki do cofnięcia.",
            }
        )
        thought = plan_safe_development_command(
            brain,
            "Cofnij ostatnią poprawkę projektu",
        )
        self.assertFalse(thought["can_execute"])
        self.assertFalse(thought["requires_confirmation"])
        self.assertFalse(thought["project_write"])

    def test_execution_uses_exact_session_and_fingerprint(self) -> None:
        brain = self._brain()
        brain.safe_autonomous_development_service.rollback.return_value = {
            "success": True,
            "status": "ROLLED_BACK",
            "message": "Cofnąłem ostatnią poprawkę projektu.",
        }
        thought = plan_safe_development_command(
            brain,
            "Cofnij ostatnią poprawkę projektu",
        )
        message = execute_safe_development_command(brain, thought)
        brain.safe_autonomous_development_service.rollback.assert_called_once_with(
            "safe-dev-rollback-1",
            "rollback-fingerprint-1",
        )
        self.assertIn("Cofnąłem", message)
        brain._remember_execution.assert_called_once()

    def test_deploy_command_keeps_its_existing_route(self) -> None:
        brain = self._brain()
        brain.safe_autonomous_development_service.plan_deploy.return_value = {
            "success": True,
            "session": {"session_id": "safe-dev-deploy-1"},
            "operation_fingerprint": "deploy-fingerprint-1",
            "confirmation_message": "Czy wdrożyć poprawkę?",
        }
        thought = plan_safe_development_command(
            brain,
            "Wdróż przygotowaną poprawkę",
        )
        self.assertEqual(thought["handler"], "safe_development_deploy")

    def test_source_bounds_and_config_are_kept(self) -> None:
        root = Path(__file__).resolve().parents[1]
        commands_path = (
            root
            / "app"
            / "ai"
            / "software_engineer"
            / "safe_development_commands.py"
        )
        source = commands_path.read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 360)
        self.assertIn('"cofnij ostatnia poprawke projektu"', source)
        config = json.loads(
            (
                root
                / "config"
                / "b210_3_natural_safe_rollback_routing.json"
            ).read_text(encoding="utf-8")
        )
        self.assertFalse(config["safety"]["auto_approve"])
        self.assertFalse(config["safety"]["auto_deploy"])
        self.assertTrue(config["safety"]["rollback_requires_confirmation"])


if __name__ == "__main__":
    unittest.main()

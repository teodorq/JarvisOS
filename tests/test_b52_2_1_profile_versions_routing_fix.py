from __future__ import annotations

import ast
from pathlib import Path
import unittest

from app.gui.command_safety import (
    is_read_only_learning_command,
    is_safe_read_only_thought,
)


class B5221ProfileVersionsRoutingFixTests(
    unittest.TestCase
):

    def test_profile_versions_is_read_only(
        self,
    ) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż wersje profilu uczenia"
            )
        )

    def test_learning_status_and_history_are_read_only(
        self,
    ) -> None:
        commands = (
            "Pokaż status uczenia autonomicznego",
            "Pokaż historię uczenia autonomicznego",
            "Wyjaśnij decyzję uczenia",
        )

        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(
                    is_read_only_learning_command(
                        command
                    )
                )

    def test_mutating_learning_commands_still_require_confirmation(
        self,
    ) -> None:
        commands = (
            "Cofnij profil uczenia",
            "Aktywuj wersję profilu profile-test",
            "Włącz automatyczny trening",
            "Wyłącz automatyczny trening",
            "Zastosuj naukę",
        )

        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(
                    is_read_only_learning_command(
                        command
                    )
                )

    def test_only_software_engineer_read_only_thought_is_safe(
        self,
    ) -> None:
        self.assertTrue(
            is_safe_read_only_thought({
                "handler": (
                    "autonomous_software_engineer"
                ),
                "command": (
                    "Pokaż wersje profilu uczenia"
                ),
            })
        )
        self.assertFalse(
            is_safe_read_only_thought({
                "handler": "project_director",
                "command": (
                    "Pokaż wersje profilu uczenia"
                ),
            })
        )

    def test_confirmation_uses_shared_safe_handler(self) -> None:
        source_path = (
            Path(__file__).resolve().parents[1]
            / "app/gui/main_window.py"
        )
        source = source_path.read_text(encoding="utf-8")
        method = source.split("def handle_confirmation", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("super().handle_confirmation(answer)", method)
        self.assertIn("handle_owner_confirmation(self, answer)", method)
        self.assertNotIn("self.brain.execute(", method)


from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.assistant.controller import PersonalAssistantController
from app.assistant.fast_local_commands import FastLocalCommandService
from app.assistant.local_clock import format_local_clock


class LocalClockTests(unittest.TestCase):
    def test_formats_polish_date_without_network(self) -> None:
        value = format_local_clock(
            "Jaki mamy dziś dzień?",
            now=datetime(2026, 10, 2, 14, 7),
        )

        self.assertEqual(value, "Dzisiaj jest piątek, 2 października 2026 roku.")

    def test_formats_combined_date_and_time(self) -> None:
        value = format_local_clock(
            "Podaj datę i godzinę",
            now=datetime(2026, 10, 2, 4, 7),
        )

        self.assertEqual(
            value,
            "Dzisiaj jest piątek, 2 października 2026 roku, "
            "a aktualna godzina to 04:07.",
        )

    def test_date_question_uses_fast_read_only_intent(self) -> None:
        with TemporaryDirectory() as directory:
            assistant = PersonalAssistantController(Path(directory))
            thought = assistant.plan("Jaki mamy dzisiaj dzień?")

            self.assertEqual(thought["assistant_intent"], "current_time")
            self.assertTrue(thought["read_only"])
            self.assertEqual(thought["actions"], [])

    def test_date_question_completes_through_fast_local_service(self) -> None:
        with TemporaryDirectory() as directory:
            assistant = PersonalAssistantController(Path(directory))

            result = FastLocalCommandService.try_execute(
                assistant,
                "Jaki mamy dzisiaj dzień?",
                authorize=lambda *_args, **_kwargs: {"allowed": True},
            )

            self.assertIsNotNone(result)
            self.assertEqual(result["handler"], "fast_local_response")
            self.assertIn("Dzisiaj jest", result["message"])

    def test_controller_matches_common_date_phrases(self) -> None:
        for command in (
            "Jaka jest data?",
            "Podaj dzisiejszą datę",
            "Jaki mamy dziś dzień?",
            "Jaki dzisiaj jest dzień tygodnia?",
            "Podaj datę i godzinę",
        ):
            with self.subTest(command=command):
                self.assertTrue(PersonalAssistantController.matches(command))


if __name__ == "__main__":
    unittest.main()

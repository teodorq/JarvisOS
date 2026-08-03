from __future__ import annotations

import re
from tempfile import TemporaryDirectory
import unittest

from app.assistant.controller import PersonalAssistantController


class LocalTimeIntentTests(unittest.TestCase):
    def test_polish_time_question_is_local_and_read_only(self) -> None:
        with TemporaryDirectory() as temporary:
            assistant = PersonalAssistantController(temporary)
            resolved = assistant.resolve_command("Która jest godzina?")
            thought = assistant.plan("Która jest godzina?")
            response = assistant.handle("Która jest godzina?")

        self.assertEqual(resolved.intent, "current_time")
        self.assertTrue(thought["read_only"])
        self.assertRegex(response, r"^Teraz jest \d{2}:\d{2}\.$")

    def test_natural_variants_are_recognized(self) -> None:
        for command in ("Jaka jest godzina?", "Podaj godzinę", "Aktualna godzina"):
            self.assertTrue(PersonalAssistantController.matches(command))


if __name__ == "__main__":
    unittest.main()

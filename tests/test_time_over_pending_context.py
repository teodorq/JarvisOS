from __future__ import annotations

import re
from tempfile import TemporaryDirectory
import unittest

from app.assistant.controller import PersonalAssistantController


class TimeOverPendingContextTests(unittest.TestCase):
    def test_time_question_is_not_used_as_missing_reminder_date(self) -> None:
        with TemporaryDirectory() as temporary:
            assistant = PersonalAssistantController(temporary)
            assistant.assistant_v12.context.set_pending(
                intent="reminder_add",
                missing=["when"],
                slots={"text": "Sprawdź raport"},
                prompt="Podaj termin.",
            )

            resolved = assistant.resolve_command("Jaka jest godzina?")
            thought = assistant.plan("Jaka jest godzina?")
            response = assistant.handle("Jaka jest godzina?")
            pending = assistant.assistant_v12.context.load()["pending"]

        self.assertEqual(resolved.intent, "current_time")
        self.assertEqual(thought["assistant_intent"], "current_time")
        self.assertTrue(thought["read_only"])
        self.assertRegex(response, r"^Teraz jest \d{2}:\d{2}\.$")
        self.assertEqual(pending["intent"], "reminder_add")
        self.assertEqual(pending["slots"]["text"], "Sprawdź raport")


if __name__ == "__main__":
    unittest.main()

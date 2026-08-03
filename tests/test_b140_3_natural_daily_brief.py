from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.assistant_v12.daily_brief_formatter import DailyBriefFormatter
from app.assistant_v12.controller import AssistantV12Controller


class B1403NaturalDailyBriefTests(unittest.TestCase):
    def test_raw_zeroes_and_brak_are_not_shown(self) -> None:
        result = DailyBriefFormatter.format(
            {
                "mail": {
                    "draft_count": 1,
                    "high_priority_count": 0,
                },
                "calendar": {
                    "upcoming_count": 0,
                    "next_event": {},
                },
                "reminders": {
                    "pending_count": 1,
                    "due_count": 1,
                    "next_reminder": {
                        "text": "Sprawdź raport produktywności",
                    },
                },
            }
        )

        self.assertIn("Twój dzień", result)
        self.assertIn("Najważniejsze teraz", result)
        self.assertIn("Sprawdź raport produktywności", result)
        self.assertIn("Nie masz zaplanowanych spotkań", result)
        self.assertIn("1 szkic", result)
        self.assertNotIn("spotkania 0", result)
        self.assertNotIn("„brak”", result.casefold())

    def test_next_event_is_presented_as_the_priority(self) -> None:
        result = DailyBriefFormatter.format(
            {
                "mail": {"draft_count": 0},
                "calendar": {
                    "upcoming_count": 2,
                    "next_event": {
                        "title": "Odbiór instalacji",
                        "start_at": "2030-07-20T10:30:00+00:00",
                    },
                },
                "reminders": {
                    "pending_count": 0,
                    "due_count": 0,
                    "next_reminder": {},
                },
            }
        )

        self.assertIn("Najbliższe spotkanie", result)
        self.assertIn("Odbiór instalacji", result)
        self.assertNotIn("brak", result.casefold())

    def test_empty_day_gets_a_useful_suggestion(self) -> None:
        result = DailyBriefFormatter.format(
            {
                "mail": {"draft_count": 0},
                "calendar": {
                    "upcoming_count": 0,
                    "next_event": {},
                },
                "reminders": {
                    "pending_count": 0,
                    "due_count": 0,
                    "next_reminder": {},
                },
            }
        )

        self.assertIn("Twój dzień jest spokojny", result)
        self.assertIn("najważniejszy cel", result)

    def test_existing_assistant_day_overview_uses_natural_brief(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            controller = AssistantV12Controller(Path(directory))
            result = controller.handle("Pokaż mój dzień")

        self.assertIn("Twój dzień", result)
        self.assertNotIn("następne „brak”", result.casefold())
        self.assertNotIn("spotkania 0", result)


if __name__ == "__main__":
    unittest.main()

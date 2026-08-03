from __future__ import annotations

from datetime import datetime
from pathlib import Path
import unittest

from app.natural_actions.revisions import rebuild_command
from app.natural_actions.temporal import PolishTemporalParser
from app.natural_actions.understanding import NaturalActionUnderstanding


FIXED_NOW = datetime(2026, 7, 27, 12, 0).astimezone()


class B1506CalendarTitleCleanupTests(unittest.TestCase):
    def parser(self) -> PolishTemporalParser:
        return PolishTemporalParser(lambda: FIXED_NOW)

    def understanding(self) -> NaturalActionUnderstanding:
        return NaturalActionUnderstanding(self.parser())

    def test_iso_date_is_removed_as_one_token(self) -> None:
        clean = self.parser().strip_temporal(
            "Dodaj trening 2026-07-28 o 19:00"
        )
        self.assertEqual(clean, "Dodaj trening")
        self.assertNotIn("2026", clean)

    def test_rebuilt_revision_keeps_date_out_of_title(self) -> None:
        thought = {
            "assistant_intent": "calendar_create",
            "natural_slots": {
                "title": "trening",
                "when": "2026-07-28T18:00:00+02:00",
                "duration_minutes": 60,
            },
        }
        command = rebuild_command(thought, "nie, jednak o 19")
        request = self.understanding().parse(command)
        when = datetime.fromisoformat(request.slots["when"])

        self.assertEqual(request.slots["title"], "trening")
        self.assertEqual((when.year, when.month, when.day), (2026, 7, 28))
        self.assertEqual((when.hour, when.minute), (19, 0))

    def test_regular_iso_calendar_command_has_clean_title(self) -> None:
        request = self.understanding().parse(
            "Dodaj wizytę u dentysty 2026-08-03 o 09:30"
        )
        self.assertEqual(request.slots["title"], "wizytę u dentysty")
        self.assertNotIn("2026", request.slots["title"])

    def test_source_limit_and_no_hardcoded_project_path(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/natural_actions/temporal.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(source.splitlines()), 270)
        self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

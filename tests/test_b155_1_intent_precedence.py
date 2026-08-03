from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from tests.test_b151_b155_daily_actions import FakeOnline, FIXED_NOW
from app.natural_actions.service import NaturalActionService
from app.natural_actions.temporal import PolishTemporalParser
from app.natural_actions.understanding import NaturalActionUnderstanding


class B1551IntentPrecedenceTests(unittest.TestCase):

    def service(self, directory: str) -> NaturalActionService:
        return NaturalActionService(
            directory,
            online=FakeOnline(directory),
            now_provider=lambda: FIXED_NOW,
        )

    def test_explicit_calendar_create_overrides_stale_update_pending(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            missing = service.handle(
                "Przenieś jutrzejszą wizytę na 20"
            )
            plan = service.plan(
                "Dodaj jutro trening o 18"
            )

        self.assertIn("Nie znalazłem", missing)
        self.assertEqual(
            plan["assistant_intent"],
            "calendar_create",
        )
        self.assertTrue(plan["requires_confirmation"])
        self.assertNotIn(
            "event_match",
            plan["natural_slots"],
        )

    def test_explicit_mail_action_overrides_stale_calendar_pending(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            service.handle(
                "Usuń jutrzejszą wizytę"
            )
            plan = service.plan(
                "Napisz do teodorq7@gmail.com, że będę później"
            )

        self.assertEqual(
            plan["assistant_intent"],
            "mail_draft",
        )
        self.assertEqual(
            plan["natural_slots"]["recipient_email"],
            "teodorq7@gmail.com",
        )

    def test_short_answer_continues_existing_pending_action(self) -> None:
        understanding = NaturalActionUnderstanding(
            PolishTemporalParser(lambda: FIXED_NOW)
        )
        pending = {
            "intent": "calendar_update",
            "slots": {
                "event_query": "trening",
                "search_date": "2026-07-28",
            },
        }

        request = understanding.parse(
            "o 20",
            pending=pending,
        )

        self.assertEqual(request.intent, "calendar_update")
        self.assertTrue(request.used_context)
        self.assertIn("new_when", request.slots)

    def test_create_without_pending_stays_create(self) -> None:
        understanding = NaturalActionUnderstanding(
            PolishTemporalParser(lambda: FIXED_NOW)
        )
        request = understanding.parse(
            "Dodaj jutro trening o 18"
        )
        self.assertEqual(request.intent, "calendar_create")
        self.assertFalse(request.used_context)


if __name__ == "__main__":
    unittest.main()

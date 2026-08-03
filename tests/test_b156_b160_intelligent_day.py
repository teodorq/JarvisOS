from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.service import NaturalActionService
from app.natural_actions.understanding import NaturalActionUnderstanding


class FakeProvider:
    pass


class FakeGmail:
    def __init__(self) -> None:
        self.calls = 0

    def priority(self, _limit: int = 5):
        self.calls += 1
        return [{
            "id": "mail-1",
            "subject": "Pilna odpowiedź dla klienta",
            "from": "klient@example.com",
        }]


class FakeCalendar:
    def __init__(self) -> None:
        self.calls = []

    def find_events(self, _query, *, start_at, end_at, max_results=20):
        self.calls.append((start_at, end_at, max_results))
        event_at = start_at + timedelta(hours=10)
        return [{
            "id": "event-1",
            "title": "Spotkanie z klientem",
            "start_at": event_at.isoformat(),
            "end_at": (event_at + timedelta(hours=1)).isoformat(),
        }]


class FakeReminders:
    def status(self):
        now = datetime.now().astimezone()
        return {
            "pending_count": 1,
            "due_count": 1,
            "next_reminder": {
                "text": "Sprawdź ofertę",
                "due_at": (now + timedelta(minutes=15)).isoformat(),
            },
        }


class FakeOnline:
    def __init__(self, root: str) -> None:
        self.project_root = Path(root)
        self.provider = FakeProvider()
        self.gmail = FakeGmail()
        self.calendar = FakeCalendar()
        self.reminders = FakeReminders()


class B156B160IntelligentDayTests(unittest.TestCase):
    def service(self, root: str) -> NaturalActionService:
        return NaturalActionService(root, online=FakeOnline(root))

    def test_b156_varied_day_phrases_route_semantically(self) -> None:
        examples = {
            "Co mam dzisiaj?": "day_overview",
            "Pokaż mój dzień": "day_overview",
            "Podsumuj mi dzień": "day_review",
            "Pokaż centrum dnia online": "day_overview",
        }
        for command, expected_intent in examples.items():
            with self.subTest(command=command):
                intent, confidence = NaturalActionUnderstanding.classify(command)
                self.assertEqual(intent, expected_intent)
                self.assertGreaterEqual(confidence, 0.9)

    def test_b156_overview_combines_calendar_mail_and_reminders(self) -> None:
        with TemporaryDirectory() as directory:
            response = self.service(directory).handle("Pokaż mój dzień")
        self.assertIn("Twój dzień:", response)
        self.assertIn("Sprawdź ofertę", response)
        self.assertIn("Spotkanie z klientem", response)
        self.assertIn("Pilna odpowiedź dla klienta", response)
        self.assertNotIn("B156", response)
        self.assertNotIn("status", response.casefold())

    def test_b157_now_priority_is_direct_and_useful(self) -> None:
        with TemporaryDirectory() as directory:
            response = self.service(directory).handle(
                "Co powinienem zrobić teraz?"
            )
        self.assertTrue(response.startswith("Teraz zajmij się:"))
        self.assertIn("Sprawdź ofertę", response)

    def test_b157_reaction_phrasing_generalizes(self) -> None:
        examples = (
            "Co jest najważniejsze?",
            "Czym mam się zająć?",
            "Co wymaga reakcji dzisiaj?",
            "Od czego zacząć?",
        )
        for command in examples:
            with self.subTest(command=command):
                self.assertEqual(
                    NaturalActionUnderstanding.classify(command)[0],
                    "day_priority",
                )

    def test_b158_tomorrow_plan_uses_tomorrow_window(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            response = service.handle("Uporządkuj mi jutro")
            start = service.online.calendar.calls[-1][0]
        self.assertEqual(
            start.date(),
            datetime.now().astimezone().date() + timedelta(days=1),
        )
        self.assertIn("Plan na jutro:", response)
        self.assertIn("Spotkanie z klientem", response)
        self.assertIn("bez automatycznych zmian", response)

    def test_b158_day_plan_is_read_only(self) -> None:
        with TemporaryDirectory() as directory:
            plan = self.service(directory).plan("Zaplanuj mi jutro")
        self.assertTrue(plan["read_only"])
        self.assertFalse(plan["requires_confirmation"])

    def test_b159_mark_done_requires_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            plan = self.service(directory).plan(
                "Oznacz raport jako zrobione"
            )
        self.assertEqual(plan["assistant_intent"], "day_mark_done")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("raport", plan["confirmation_message"])

    def test_b159_completed_item_is_remembered(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            result = service.handle("Zrobiłem raport dla klienta")
            history = service.handle("Co zrobiłem dzisiaj?")
        self.assertIn("raport dla klienta", result)
        self.assertIn("raport dla klienta", history)

    def test_b159_history_includes_real_completed_actions(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            request = service.understanding.parse(
                "Dodaj jutro trening o osiemnastej"
            )
            request.slots["event_id"] = "event-1"
            service.context.remember(request, "Dodałem trening.")
            history = service.handle("Co już zrobiłem?")
        self.assertIn("dodano wydarzenie do kalendarza", history)

    def test_b160_read_only_failures_degrade_without_technical_errors(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            online.gmail.priority = lambda _limit=5: (_ for _ in ()).throw(
                RuntimeError("TOKEN_SECRET")
            )
            response = NaturalActionService(
                directory, online=online
            ).handle("Pokaż mój dzień")
        self.assertIn("Twój dzień:", response)
        self.assertNotIn("TOKEN_SECRET", response)
        self.assertNotIn("RuntimeError", response)

    def test_b160_stage_status_and_safety_contract(self) -> None:
        with TemporaryDirectory() as directory:
            status = self.service(directory).status()
        for stage in ("B156", "B157", "B158", "B159", "B160"):
            self.assertIn(stage, status["stages"])
        self.assertTrue(status["writes_require_confirmation"])
        self.assertFalse(status["automatic_sending"])

    def test_b160_source_limits_and_no_hardcoded_project_path(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/service.py": 320,
            "app/natural_actions/understanding.py": 300,
            "app/natural_actions/advanced_understanding.py": 220,
            "app/natural_actions/advanced_actions.py": 190,
            "app/natural_actions/runtime.py": 140,
            "app/natural_actions/daily_intelligence.py": 320,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

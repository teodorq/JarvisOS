from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.day_quality import IntelligentDayQuality
from app.natural_actions.service import NaturalActionService


class FakeGmail:
    def __init__(self, messages):
        self.messages = list(messages)

    def priority(self, _limit=5):
        return list(self.messages)


class FakeCalendar:
    def __init__(self, events=None):
        self.events = list(events or [])

    def find_events(self, _query, *, start_at, end_at, max_results=20):
        return list(self.events)


class FakeReminders:
    def __init__(self, due=0, text=""):
        self.due = due
        self.text = text

    def status(self):
        result = {"pending_count": self.due, "due_count": self.due}
        if self.text:
            result["next_reminder"] = {
                "text": self.text,
                "due_at": (datetime.now().astimezone() + timedelta(minutes=20)).isoformat(),
            }
        return result


class FakeOnline:
    def __init__(self, root, *, mail=None, events=None, due=0, reminder=""):
        self.project_root = Path(root)
        self.provider = object()
        self.gmail = FakeGmail(mail or [])
        self.calendar = FakeCalendar(events)
        self.reminders = FakeReminders(due, reminder)


class B1601IntelligentDayQualityTests(unittest.TestCase):
    def service(self, root, **kwargs):
        return NaturalActionService(root, online=FakeOnline(root, **kwargs))

    def test_sanitizer_removes_emoji_and_invalid_symbols(self):
        result = IntelligentDayQuality.clean_text(
            "Ważne 🍭📌 \ufffd spotkanie ✅ jutro"
        )
        self.assertEqual(result, "Ważne spotkanie jutro")

    def test_marketing_message_is_not_reported_as_important(self):
        mail = [{
            "subject": "Wybór należy do Ciebie 🍭🍭",
            "from": "newsletter@example.com",
            "snippet": "Promocja tylko dziś. Kup teraz.",
            "unread": True,
            "important": True,
        }]
        with TemporaryDirectory() as directory:
            response = self.service(directory, mail=mail).handle("Pokaż mój dzień")
        self.assertNotIn("Wybór należy", response)
        self.assertNotIn("Ważna poczta", response)

    def test_actionable_mail_is_kept_and_ranked_first(self):
        mail = [
            {
                "subject": "Newsletter tygodniowy",
                "from": "newsletter@example.com",
                "snippet": "Promocja i rabat",
                "unread": True,
                "important": True,
            },
            {
                "subject": "Pilna odpowiedź dla klienta",
                "from": "klient@example.com",
                "snippet": "Proszę o potwierdzenie terminu.",
                "unread": True,
                "important": True,
            },
        ]
        ranked = IntelligentDayQuality.rank_mail(mail)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["subject"], "Pilna odpowiedź dla klienta")

    def test_singular_reminder_uses_correct_polish_form(self):
        with TemporaryDirectory() as directory:
            response = self.service(
                directory,
                due=1,
                reminder="Sprawdź raport",
            ).handle("Pokaż mój dzień")
        self.assertIn("Masz 1 pilne przypomnienie.", response)
        self.assertNotIn("1 pilne przypomnienia", response)

    def test_event_plural_forms_are_correct(self):
        self.assertEqual(IntelligentDayQuality.event_count(1), "1 wydarzenie")
        self.assertEqual(IntelligentDayQuality.event_count(3), "3 wydarzenia")
        self.assertEqual(IntelligentDayQuality.event_count(12), "12 wydarzeń")

    def test_empty_tomorrow_plan_is_concrete(self):
        with TemporaryDirectory() as directory:
            response = self.service(directory).handle("Uporządkuj mi jutro")
        self.assertIn("1. rano", response)
        self.assertIn("2. pierwszy blok pracy", response)
        self.assertIn("3. wieczorem", response)
        self.assertIn("bez automatycznych zmian", response)

    def test_tomorrow_plan_numbers_real_events(self):
        now = datetime.now().astimezone()
        event = {
            "title": "Spotkanie z klientem 📌",
            "start_at": (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
        }
        with TemporaryDirectory() as directory:
            response = self.service(directory, events=[event]).handle(
                "Uporządkuj mi jutro"
            )
        self.assertIn("1. 10:00 — Spotkanie z klientem", response)
        self.assertNotIn("📌", response)

    def test_source_limits_and_project_path_policy(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/daily_intelligence.py": 320,
            "app/natural_actions/day_quality.py": 180,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

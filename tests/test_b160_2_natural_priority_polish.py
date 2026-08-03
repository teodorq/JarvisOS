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
                "due_at": (
                    datetime.now().astimezone() + timedelta(minutes=20)
                ).isoformat(),
            }
        return result


class FakeOnline:
    def __init__(self, root, *, mail=None, events=None, due=0, reminder=""):
        self.project_root = Path(root)
        self.provider = object()
        self.gmail = FakeGmail(mail or [])
        self.calendar = FakeCalendar(events)
        self.reminders = FakeReminders(due, reminder)


class B1602NaturalPriorityPolishTests(unittest.TestCase):
    def service(self, root, **kwargs):
        return NaturalActionService(root, online=FakeOnline(root, **kwargs))

    def test_vague_promotional_delivery_is_filtered(self):
        mail = [{
            "subject": "Specjalna dostawa",
            "from": "oferty@sklep.example",
            "snippet": "Niespodzianka czeka na Ciebie. Nie przegap.",
            "unread": True,
            "important": True,
        }]
        self.assertEqual(IntelligentDayQuality.rank_mail(mail), [])

    def test_real_delivery_status_is_kept(self):
        mail = [{
            "subject": "Status przesyłki nr 123",
            "from": "powiadomienia@kurier.example",
            "snippet": "Doręczenie przesyłki planowane jest jutro.",
            "unread": True,
            "important": False,
        }]
        ranked = IntelligentDayQuality.rank_mail(mail)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["subject"], "Status przesyłki nr 123")

    def test_social_notification_is_not_treated_as_priority_mail(self):
        mail = [{
            "subject": "_.zakrzewska właśnie wysłał(a) Ci wiadomość",
            "from": '"_.zakrzewska na TikToku" <notification@service.tiktok.com>',
            "snippet": "Kacper Zakrzewski, odpowiedz na TikToku.",
            "unread": False,
            "important": True,
        }]
        self.assertEqual(IntelligentDayQuality.rank_mail(mail), [])

    def test_overview_does_not_repeat_mail_selected_as_next_action(self):
        mail = [{
            "subject": "Pilna odpowiedź dla klienta",
            "from": "klient@example.com",
            "snippet": "Proszę o potwierdzenie terminu.",
            "unread": True,
            "important": True,
        }]
        with TemporaryDirectory() as directory:
            response = self.service(directory, mail=mail).handle("Pokaż mój dzień")
        self.assertEqual(response.count("Pilna odpowiedź dla klienta"), 1)

    def test_priority_response_is_natural_and_non_promissory(self):
        with TemporaryDirectory() as directory:
            response = self.service(
                directory,
                due=1,
                reminder="Sprawdź raport produktywności",
            ).handle("Co powinienem zrobić teraz?")
        self.assertTrue(response.startswith("Teraz zajmij się:"))
        self.assertIn("Sprawdź raport produktywności", response)
        self.assertIn("powiedz mi, że to zrobione", response)
        self.assertNotIn("zrealizuj przypomnienie", response)
        self.assertNotIn("Potem sprawdzę", response)

    def test_overview_uses_cautious_mail_label(self):
        mail = [{
            "subject": "Pilna odpowiedź dla klienta",
            "from": "klient@example.com",
            "snippet": "Proszę o potwierdzenie terminu.",
            "unread": True,
            "important": True,
        }]
        with TemporaryDirectory() as directory:
            response = self.service(directory, mail=mail).handle("Pokaż mój dzień")
        self.assertIn("Wiadomość wymagająca uwagi", response)
        self.assertNotIn("Ważna poczta", response)

    def test_tomorrow_plan_has_three_concrete_steps_with_mail(self):
        mail = [{
            "subject": "Faktura do akceptacji",
            "from": "biuro@example.com",
            "snippet": "Proszę o akceptację płatności.",
            "unread": True,
            "important": True,
        }]
        with TemporaryDirectory() as directory:
            response = self.service(directory, mail=mail).handle("Uporządkuj mi jutro")
        self.assertIn("1. rano", response)
        self.assertIn("2. rano — sprawdź wiadomość", response)
        self.assertIn("3. wieczorem", response)
        self.assertIn("bez automatycznych zmian", response)

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

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.proactive_day import (
    ProactiveDayAnalyzer,
    ProactiveDayService,
)
from app.natural_actions.service import NaturalActionService


class FakeProvider:
    pass


class FakeGmail:
    def __init__(self, messages=None):
        self.messages = list(messages or [])

    def priority(self, _limit=5):
        return list(self.messages)


class FakeCalendar:
    def __init__(self, events=None):
        self.events = list(events or [])

    def find_events(self, _query, *, start_at, end_at, max_results=20):
        return list(self.events)


class FakeReminders:
    def __init__(self, *, due=0, text="", due_at=""):
        self.due = due
        self.text = text
        self.due_at = due_at

    def status(self):
        result = {"due_count": self.due, "pending_count": self.due}
        if self.text:
            result["next_reminder"] = {
                "text": self.text,
                "due_at": self.due_at,
            }
        return result


class FakeOnline:
    def __init__(
        self,
        root,
        *,
        events=None,
        mail=None,
        due=0,
        reminder="",
        reminder_at="",
    ):
        self.project_root = Path(root)
        self.provider = FakeProvider()
        self.calendar = FakeCalendar(events)
        self.gmail = FakeGmail(mail)
        self.reminders = FakeReminders(
            due=due,
            text=reminder,
            due_at=reminder_at,
        )


class B161B165ProactiveJarvisTests(unittest.TestCase):
    def now(self):
        return datetime.now().astimezone().replace(microsecond=0)

    def snapshot(self, *, events=None, mail=None, due=0, reminder=""):
        now = self.now()
        reminders = {"due_count": due, "pending_count": due}
        if reminder:
            reminders["next_reminder"] = {
                "text": reminder,
                "due_at": (now + timedelta(minutes=15)).isoformat(),
            }
        return {
            "now": now,
            "events": list(events or []),
            "mail": list(mail or []),
            "reminders": reminders,
            "completed": [],
        }

    def test_b161_startup_brief_is_shown_only_once_per_day(self):
        snapshot = self.snapshot(reminder="Sprawdź raport")
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory,
                lambda _offset: snapshot,
                now_provider=self.now,
            )
            first = service.startup_brief()
            second = service.startup_brief()
        self.assertTrue(first["should_show"])
        self.assertFalse(second["should_show"])
        self.assertRegex(first["message"], r"^(Poranny brief|Brief dnia):")

    def test_b161_force_allows_manual_refresh(self):
        snapshot = self.snapshot()
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory,
                lambda _offset: snapshot,
                now_provider=self.now,
            )
            service.startup_brief()
            refreshed = service.startup_brief(force=True)
        self.assertTrue(refreshed["should_show"])
        self.assertIn("Dzień wygląda spokojnie", refreshed["message"])

    def test_b162_detects_overlapping_calendar_events(self):
        now = self.now()
        events = [
            {
                "title": "Spotkanie z klientem",
                "start_at": (now + timedelta(hours=2)).isoformat(),
                "end_at": (now + timedelta(hours=3)).isoformat(),
            },
            {
                "title": "Odbiór materiałów",
                "start_at": (now + timedelta(hours=2, minutes=30)).isoformat(),
                "end_at": (now + timedelta(hours=3, minutes=30)).isoformat(),
            },
        ]
        analysis = ProactiveDayAnalyzer.analyze(self.snapshot(events=events))
        self.assertEqual(analysis["level"], "critical")
        self.assertEqual(len(analysis["conflicts"]), 1)
        self.assertIn("Rozwiąż konflikt", analysis["next_action"])

    def test_b162_imminent_event_is_high_attention(self):
        now = self.now()
        event = {
            "title": "Trening",
            "start_at": (now + timedelta(minutes=45)).isoformat(),
            "end_at": (now + timedelta(minutes=105)).isoformat(),
        }
        analysis = ProactiveDayAnalyzer.analyze(self.snapshot(events=[event]))
        self.assertEqual(analysis["level"], "high")
        self.assertEqual(analysis["minutes_to_event"], 45)

    def test_b163_quiet_day_does_not_request_voice_alert(self):
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory,
                lambda _offset: self.snapshot(),
                now_provider=self.now,
            )
            result = service.startup_brief()
        self.assertEqual(result["level"], "quiet")
        self.assertFalse(result["speak"])
        self.assertFalse(result["conflict_count"])

    def test_b163_due_reminder_is_selectively_urgent(self):
        daytime = self.now().replace(hour=12, minute=0, second=0)
        snapshot = self.snapshot(
            due=1,
            reminder="Zadzwoń do klienta",
        )
        snapshot["now"] = daytime
        snapshot["reminders"]["next_reminder"]["due_at"] = (
            daytime + timedelta(minutes=15)
        ).isoformat()
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory,
                lambda _offset: snapshot,
                now_provider=lambda: daytime,
            )
            result = service.startup_brief()
        self.assertEqual(result["level"], "critical")
        self.assertTrue(result["speak"])
        self.assertIn("Zadzwoń do klienta", result["next_action"])

    def test_b163_quiet_hours_suppress_spoken_alert(self):
        night = self.now().replace(hour=23, minute=0)
        snapshot = self.snapshot(
            due=1,
            reminder="Zadzwoń do klienta",
        )
        snapshot["now"] = night
        with TemporaryDirectory() as directory:
            service = ProactiveDayService(
                directory,
                lambda _offset: snapshot,
                now_provider=lambda: night,
            )
            result = service.startup_brief()
        self.assertEqual(result["level"], "critical")
        self.assertFalse(result["speak"])

    def test_b164_next_action_prefers_due_reminder(self):
        now = self.now()
        event = {
            "title": "Spotkanie",
            "start_at": (now + timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(hours=2)).isoformat(),
        }
        snapshot = self.snapshot(
            events=[event],
            due=1,
            reminder="Wyślij wycenę",
        )
        self.assertEqual(
            ProactiveDayAnalyzer.next_action(snapshot),
            "„Wyślij wycenę”",
        )

    def test_b164_next_action_uses_actionable_mail_when_day_is_free(self):
        mail = [{"subject": "Faktura do akceptacji"}]
        snapshot = self.snapshot(mail=mail)
        self.assertIn(
            "Faktura do akceptacji",
            ProactiveDayAnalyzer.next_action(snapshot),
        )

    def test_b165_natural_service_exposes_proactive_stages_and_status(self):
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = NaturalActionService(directory, online=online)
            status = service.status()
        for stage in ("B161", "B162", "B163", "B164", "B165"):
            self.assertIn(stage, status["stages"])
        self.assertEqual(status["proactive"]["status"], "PROACTIVE_DAY_READY")
        self.assertFalse(status["proactive"]["automatic_writes"])

    def test_b165_startup_brief_uses_real_natural_action_snapshot(self):
        now = self.now()
        event = {
            "id": "event-1",
            "title": "Spotkanie z klientem",
            "start_at": (now + timedelta(minutes=60)).isoformat(),
            "end_at": (now + timedelta(minutes=120)).isoformat(),
        }
        mail = [{
            "subject": "Pilna odpowiedź dla klienta",
            "from": "klient@example.com",
            "snippet": "Proszę o potwierdzenie terminu.",
            "important": True,
            "unread": True,
        }]
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=[event], mail=mail),
            )
            result = service.startup_brief(force=True)
        self.assertTrue(result["should_show"])
        self.assertIn("Spotkanie z klientem", result["message"])
        self.assertIn("Pilna odpowiedź dla klienta", result["message"])

    def test_b165_client_shell_schedules_brief_without_owner_console_copy(self):
        root = Path(__file__).resolve().parents[1]
        mixin = (root / "app/gui/client_online_mixin.py").read_text(
            encoding="utf-8"
        )
        client = (root / "app/gui/client_experience_window.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_schedule_proactive_brief", mixin)
        self.assertIn("natural.startup_brief()", mixin)
        self.assertIn("_on_client_event", mixin)
        self.assertIn("15 * 60 * 1000", mixin)
        self.assertIn("pending_thought", mixin)
        self.assertNotIn("console_page.append", mixin)
        self.assertIn("self._schedule_proactive_brief()", client)

    def test_b165_source_limits_and_no_hardcoded_project_path(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/proactive_day.py": 300,
            "app/natural_actions/service.py": 320,
            "app/natural_actions/runtime.py": 140,
            "app/natural_actions/daily_intelligence.py": 320,
            "app/gui/client_online_mixin.py": 140,
            "app/gui/client_experience_window.py": 440,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

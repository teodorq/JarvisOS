from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.business.daily_metrics import DailyBusinessMetrics
from app.gui.client_external_activity import view_mode_for_thought
from app.gui.client_result_formatter import ClientResultFormatter
from app.gui.client_window_mode import FloatingJarvisEye
from app.natural_actions.business_day_intelligence import BusinessDayIntelligenceService
from app.natural_actions.business_day_understanding import classify_business_day
from app.natural_actions.day_business_sources import EmailFinancialAnalyzer
from app.natural_actions.models import NaturalActionRequest


class _Calendar:
    def today(self):
        return [{"title": "Rozmowa z klientem", "start_at": "2026-08-02T10:00:00+02:00"}]


class _Gmail:
    def latest(self, _limit=12):
        return [{
            "subject": "Plus GSM - rachunek 129,99 PLN",
            "from": "ebok@plus.pl",
            "snippet": "Abonament do zaplaty: 129,99 PLN",
            "important": True,
            "unread": True,
        }]

    def daily_activity(self):
        return {"sent_today": 2, "pending_drafts": 1, "automatic_replies": 0}


class _Drive:
    def recent(self, _limit=8):
        return [{"id": "drive-1", "name": "Oferta dla klienta.docx"}]


class _Reminders:
    def status(self):
        return {
            "pending_count": 1,
            "due_count": 1,
            "next_reminder": {"text": "Sprawdz raport"},
        }


class _Provider:
    def list_gmail_messages(self, **_kwargs):
        return _Gmail().latest()


class _Daily:
    def _completed_for(self, _day):
        return []

    def _actions_for(self, _day):
        return []

    def _priority(self, _snapshot):
        return ""

    def _moment(self, _value):
        return "o 10:00"


class DailyBusinessOverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_natural_commands_route_to_real_sources(self):
        cases = {
            "Jaki jest mój plan dnia?": "day_overview",
            "Jak minął dzień?": "day_review",
            "Co mam dziś w kalendarzu?": "calendar_today_overview",
            "Pokaż ostatnie dokumenty": "documents_recent",
            "Pokaż przypomnienia": "reminders_overview",
            "Podlicz rachunki do zapłaty": "bills_overview",
            "Ile wydaliśmy na reklamy?": "advertising_overview",
            "Jaki był wynik tradingu?": "trading_overview",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(classify_business_day(command)[0], expected)

    def test_bill_and_ad_amounts_are_exact_not_invented(self):
        result = EmailFinancialAnalyzer.analyze([
            {"subject": "Rachunek Plus 129,99 PLN", "snippet": "abonament"},
            {"subject": "Google Ads", "snippet": "kampania 45.50 USD"},
        ])
        self.assertEqual(result["bill_totals"], {"PLN": 129.99})
        self.assertEqual(result["advertising_totals"], {"USD": 45.5})

    def test_full_day_joins_calendar_mail_documents_reminders_and_finance(self):
        with TemporaryDirectory() as directory:
            online = SimpleNamespace(
                project_root=Path(directory), provider=_Provider(),
                calendar=_Calendar(), gmail=_Gmail(), drive=_Drive(),
                reminders=_Reminders(),
            )
            service = BusinessDayIntelligenceService(object(), online, _Daily())
            request = NaturalActionRequest("Jak minął dzień?", "", "day_business_summary")
            answer = service.execute(request)
        for marker in (
            "Kalendarz:", "Poczta:", "Dokumenty:", "Przypomnienia:",
            "Rachunki:", "Reklamy:", "Trading:",
        ):
            self.assertIn(marker, answer)
        self.assertIn("Oferta dla klienta.docx", answer)
        self.assertIn("129.99 PLN", answer)
        self.assertIn("nie jest jeszcze podłączone", answer)

    def test_bill_command_writes_a_notepad_ready_report(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            online = SimpleNamespace(
                project_root=root, provider=_Provider(), calendar=_Calendar(),
                gmail=_Gmail(), drive=_Drive(), reminders=_Reminders(),
            )
            service = BusinessDayIntelligenceService(object(), online, _Daily())
            request = NaturalActionRequest("Rachunki", "", "bills_overview")
            answer = service.execute(request)
            report = root / "AI_PLIKI" / "finanse" / "RACHUNKI_DZISIAJ.txt"
            self.assertTrue(report.exists())
            self.assertIn("129.99 PLN", report.read_text(encoding="utf-8"))
            self.assertIn("Notatniku", answer)

    def test_disconnected_trading_never_reports_a_fake_result(self):
        with TemporaryDirectory() as directory:
            snapshot = DailyBusinessMetrics(directory).snapshot(date.today())["trading"]
        self.assertFalse(snapshot["connected"])
        self.assertEqual(snapshot["totals"], {})

    def test_connected_metrics_use_only_records_from_selected_day(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data" / "business" / "daily_metrics.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"sources": {"trading": {
                "connected": True,
                "records": [
                    {"date": "2026-08-02", "profit": 125.5, "currency": "PLN"},
                    {"date": "2026-08-01", "profit": 999, "currency": "PLN"},
                ],
            }}}), encoding="utf-8")
            result = DailyBusinessMetrics(root).snapshot(date(2026, 8, 2))["trading"]
        self.assertEqual(result["totals"], {"PLN": 125.5})
        self.assertEqual(result["record_count"], 1)

    def test_external_commands_use_pupil_but_local_summary_stays_in_conversation(self):
        for intent in ("calendar_today_overview", "documents_recent", "bills_overview"):
            with self.subTest(intent=intent):
                self.assertEqual(view_mode_for_thought({"assistant_intent": intent}), "pupil")
        for owner_intent in ("day_business_summary", "advertising_overview", "trading_overview"):
            with self.subTest(owner_intent=owner_intent):
                self.assertEqual(view_mode_for_thought({"assistant_intent": owner_intent}), "conversation")

    def test_pupil_uses_the_same_state_colours_as_the_main_jarvis(self):
        eye = FloatingJarvisEye()
        eye.set_state("speaking", 100)
        self.assertEqual(eye.halo.state, "speaking")
        self.assertIn("#B47CFF", eye.styleSheet())
        eye.set_state("error", 0)
        self.assertIn("#FF6678", eye.styleSheet())
        eye.close()

    def test_full_day_response_is_spoken_not_reduced_to_one_line(self):
        body = "Kalendarz: spotkanie.\nPoczta: jedna wiadomość.\nDokumenty: oferta.docx."
        card = ClientResultFormatter.format(body, result_type="day")
        self.assertEqual(card.spoken, body)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

from app.assistant.natural_language import fold_text
from app.core.project_paths import resolve_project_root
from app.productivity.calendar_center import LocalCalendarCenter
from app.productivity.daily_briefing import DailyProductivityBriefing
from app.productivity.document_center import LocalDocumentCenter
from app.productivity.mail_center import LocalMailCenter
from app.productivity.reminder_center import ReminderCenterV2


class ProductivitySuiteController:
    """B106-B110 local productivity services without hidden cloud actions."""

    STAGES = {
        "B106": "LOCAL_MAIL_CENTER_READY",
        "B107": "LOCAL_CALENDAR_READY",
        "B108": "LOCAL_DOCUMENT_CENTER_READY",
        "B109": "REMINDER_CENTER_2_READY",
        "B110": "DAILY_PRODUCTIVITY_REPORTING_READY",
    }

    READ_ONLY = {
        "suite_status", "mail_status", "calendar_status", "calendar_conflicts",
        "document_status", "document_search", "reminder_status", "report_status",
        "report_review",
    }

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.mail = LocalMailCenter(self.project_root)
        self.calendar = LocalCalendarCenter(self.project_root)
        self.documents = LocalDocumentCenter(self.project_root)
        self.reminders = ReminderCenterV2(self.project_root)
        self.reporting = DailyProductivityBriefing(
            self.project_root,
            mail=self.mail,
            calendar=self.calendar,
            documents=self.documents,
            reminders=self.reminders,
        )

    @staticmethod
    def matches(command: object) -> bool:
        value = fold_text(command)
        phrases = (
            "status b106", "centrum poczty", "status poczty", "szkic email",
            "oznacz szkic gotowy", "eksportuj szkic email", "status b107",
            "centrum kalendarza", "status kalendarza", "dodaj spotkanie demo",
            "sprawdz konflikty kalendarza", "status b108", "centrum dokumentow",
            "status dokumentow", "utworz dokument demo", "skanuj dokumenty",
            "znajdz dokument", "status b109", "centrum przypomnien 2",
            "status przypomnien 2", "najblizsze przypomnienia",
            "pokaz przypomnienia", "moje przypomnienia",
            "jakie mam przypomnienia", "dodaj przypomnienie b109",
            "zakoncz przypomnienie b109",
            "status b110", "raport produktywnosci", "generuj raport dnia",
            "podsumowanie produktywnosci", "plan na nastepny dzien",
            "status b106-b110", "centrum produktywnosci",
            "produktywnosc i organizacja",
        )
        return any(phrase in value for phrase in phrases)

    def plan(self, command: object) -> dict[str, Any]:
        intent = self.intent(command)
        return {
            "command": str(command),
            "goal": "Obsłużyć lokalne funkcje produktywności B106–B110",
            "plan": [
                "Rozpoznać pocztę, kalendarz, dokumenty, przypomnienia albo raport",
                "Odczytać trwały stan i sprawdzić ograniczenia lokalne",
                "Sprawdzić ryzyko i wymóg jawnego potwierdzenia",
                "Wykonać ograniczoną operację bez ukrytego dostępu do chmury",
                "Zapisać wynik, SHA-256 albo raport w katalogu JARVIS OS",
            ],
            "actions": [],
            "can_execute": True,
            "handler": "personal_assistant",
            "assistant_intent": intent,
            "read_only": intent in self.READ_ONLY,
        }

    def handle(self, command: object) -> str:
        text = " ".join(str(command).split()).strip()
        intent = self.intent(text)
        if intent == "suite_status":
            return self._full_status()
        if intent == "mail_status":
            return self._mail_status()
        if intent == "mail_demo":
            draft = self.mail.create_draft(
                "kontakt@example.com",
                "Raport JARVIS OS",
                "Dzień dobry, w załączniku znajdzie się lokalny raport JARVIS OS.",
                priority="HIGH",
            )
            return f"B106: utworzono szkic „{draft['subject']}” do {draft['recipient']}."
        if intent == "mail_ready":
            draft = self.mail.mark_ready()
            return f"B106: szkic {draft['draft_id']} gotowy do lokalnego eksportu."
        if intent == "mail_export":
            draft = self.mail.export_ready()
            return f"B106: wyeksportowano EML: {draft['export_path']}"
        if intent == "calendar_status":
            return self._calendar_status()
        if intent == "calendar_demo":
            event = self.calendar.add_demo()
            return f"B107: zapisano spotkanie „{event['title']}” na {event['start_at']}."
        if intent == "calendar_conflicts":
            conflicts = self.calendar.conflicts()
            return f"B107: konflikty kalendarza: {len(conflicts)}."
        if intent == "document_status":
            return self._document_status()
        if intent == "document_demo":
            path = self.documents.create_demo()
            result = self.documents.scan(path.parent)
            return f"B108: utworzono {path.name}; zeskanowano {result['scanned']} plików."
        if intent == "document_scan":
            result = self.documents.scan()
            return f"B108: skan zakończony; pliki {result['scanned']}, pominięte {result['skipped']}."
        if intent == "document_search":
            query = self._after_colon(text) or "JARVIS"
            results = self.documents.search(query)
            return "B108: " + (" | ".join(item["name"] for item in results[:5]) if results else "brak dokumentów.")
        if intent == "reminder_status":
            return self._reminder_status()
        if intent == "reminder_demo":
            reminder = self.reminders.add("Sprawdź raport produktywności", minutes=5, recurrence="DAILY")
            return f"B109: dodano przypomnienie na {reminder['due_at']} ({reminder['recurrence']})."
        if intent == "reminder_complete":
            reminder = self.reminders.complete()
            return f"B109: zapisano wykonanie; status {reminder['status']}, termin {reminder['due_at']}."
        if intent == "report_review":
            return self._report_review()
        if intent == "report_status":
            return self._report_status()
        if intent == "report_export":
            report = self.reporting.export()
            return f"B110: raport zapisany: {report['text_path']}"
        return self._full_status()

    def status(self) -> dict[str, Any]:
        return {
            "status": "DAILY_PRODUCTIVITY_SUITE_READY",
            "stages": dict(self.STAGES),
            "mail": self.mail.status(),
            "calendar": self.calendar.status(),
            "documents": self.documents.status(),
            "reminders": self.reminders.status(),
            "reporting": self.reporting.status(),
            "safety": {
                "auto_approve": False,
                "remote_mail_delivery": False,
                "remote_calendar_sync": False,
                "remote_document_indexing": False,
                "max_active_executions": 1,
            },
        }

    @staticmethod
    def intent(command: object) -> str:
        value = fold_text(command)
        if any(item in value for item in ("status b106-b110", "centrum produktywnosci", "produktywnosc i organizacja")):
            return "suite_status"
        if "utworz szkic email" in value or "szkic email demo" in value:
            return "mail_demo"
        if "oznacz szkic gotowy" in value:
            return "mail_ready"
        if "eksportuj szkic email" in value:
            return "mail_export"
        if "status b106" in value or "status poczty" in value or "centrum poczty" in value:
            return "mail_status"
        if "dodaj spotkanie demo" in value:
            return "calendar_demo"
        if "konflikty kalendarza" in value:
            return "calendar_conflicts"
        if "status b107" in value or "status kalendarza" in value or "centrum kalendarza" in value:
            return "calendar_status"
        if "utworz dokument demo" in value:
            return "document_demo"
        if "skanuj dokumenty" in value:
            return "document_scan"
        if "znajdz dokument" in value:
            return "document_search"
        if "status b108" in value or "status dokumentow" in value or "centrum dokumentow" in value:
            return "document_status"
        if "dodaj przypomnienie b109" in value:
            return "reminder_demo"
        if "zakoncz przypomnienie b109" in value:
            return "reminder_complete"
        reminder_queries = (
            "status b109", "status przypomnien 2", "centrum przypomnien 2",
            "najblizsze przypomnienia", "pokaz przypomnienia",
            "moje przypomnienia", "jakie mam przypomnienia",
        )
        if any(item in value for item in reminder_queries):
            return "reminder_status"
        if any(item in value for item in (
            "sprawdz raport produktywnosci",
            "przejrzyj raport produktywnosci",
            "pokaz podsumowanie produktywnosci",
        )):
            return "report_review"
        if "generuj raport dnia" in value or "eksportuj raport produktywnosci" in value or "plan na nastepny dzien" in value:
            return "report_export"
        if "status b110" in value or "status raportu produktywnosci" in value or "raport produktywnosci" in value:
            return "report_status"
        return "suite_status"

    def _full_status(self) -> str:
        status = self.status()
        return (
            "B106–B110: lokalna poczta, kalendarz, dokumenty, przypomnienia i raport GOTOWE. "
            f"Szkice {status['mail']['draft_count']}; wydarzenia {status['calendar']['event_count']}; "
            f"dokumenty {status['documents']['document_count']}; przypomnienia {status['reminders']['pending_count']}; "
            f"raporty {status['reporting']['report_count']}."
        )

    def _mail_status(self) -> str:
        value = self.mail.status()
        return (
            f"B106: {value['status']}; szkice {value['draft_count']}; gotowe {value['ready_count']}; "
            f"eksporty {value['exported_count']}; wysyłka zdalna NIE."
        )

    def _calendar_status(self) -> str:
        value = self.calendar.status()
        event = dict(value.get("next_event", {}) or {})
        return (
            f"B107: {value['status']}; wydarzenia {value['event_count']}; "
            f"konflikty {value['conflict_count']}; następne {event.get('title') or 'BRAK'}."
        )

    def _document_status(self) -> str:
        value = self.documents.status()
        return (
            f"B108: {value['status']}; dokumenty {value['document_count']}; "
            f"z treścią {value['text_document_count']}; chmura NIE."
        )

    def _reminder_status(self) -> str:
        value = self.reminders.status()
        pending = int(value.get("pending_count", 0) or 0)
        due = int(value.get("due_count", 0) or 0)
        if not pending:
            return "Nie masz żadnych oczekujących przypomnień."
        opening = (
            "Masz jedno oczekujące przypomnienie."
            if pending == 1
            else f"Masz {pending} oczekujących przypomnień."
        )
        details = f" {due} wymaga już uwagi." if due else ""
        reminder = dict(value.get("next_reminder", {}) or {})
        text = str(reminder.get("text") or "").strip()
        raw_moment = str(reminder.get("due_at") or "")
        try:
            moment = datetime.fromisoformat(
                raw_moment.replace("Z", "+00:00")
            ).astimezone().strftime("%d.%m o %H:%M")
        except ValueError:
            moment = raw_moment.replace("T", " ")[:16]
        next_item = f" Najbliższe: „{text}”" if text else ""
        if next_item and moment:
            next_item += f" — termin {moment}"
        return (opening + details + next_item + ".").replace("..", ".")

    def _report_review(self) -> str:
        snapshot = self.reporting.snapshot()
        mail = dict(snapshot.get("mail", {}) or {})
        calendar = dict(snapshot.get("calendar", {}) or {})
        reminders = dict(snapshot.get("reminders", {}) or {})
        return (
            "Podsumowanie produktywności: "
            f"szkice do sprawdzenia: {int(mail.get('ready_count', 0) or 0)}; "
            f"nadchodzące wydarzenia: {int(calendar.get('upcoming_count', 0) or 0)}; "
            f"pilne przypomnienia: {int(reminders.get('due_count', 0) or 0)}. "
            "Gdy skończysz, powiedz: „Oznacz raport jako zrobione”."
        )

    def _report_status(self) -> str:
        value = self.reporting.status()
        latest = dict(value.get("latest_report", {}) or {})
        report_count = int(value.get("report_count", 0) or 0)
        plan_count = int(value.get("plan_item_count", 0) or 0)
        latest_text = (
            "Ostatni raport jest zapisany lokalnie."
            if latest.get("text_path")
            else "Nie ma jeszcze zapisanego raportu."
        )
        return (
            "Raporty produktywności są gotowe. "
            f"Liczba raportów: {report_count}. "
            f"Plan zawiera {plan_count} punktów. {latest_text}"
        )

    @staticmethod
    def _after_colon(text: str) -> str:
        return text.split(":", 1)[1].strip() if ":" in text else ""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.assistant_v12.daily_brief_formatter import DailyBriefFormatter
from app.core.project_paths import resolve_project_root
from app.productivity.controller import ProductivitySuiteController


class UnifiedProductivityRouter:
    """B123 one safe router for local mail, calendar, documents and reminders."""

    WRITE_INTENTS = {
        "mail_create", "calendar_add", "document_scan",
        "reminder_add", "report_export",
    }

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.productivity = ProductivitySuiteController(self.project_root)

    def execute(self, intent: str, slots: dict[str, Any]) -> str:
        if intent == "day_overview":
            return self._day_overview()
        if intent == "mail_status":
            return self.productivity.handle("Pokaż status poczty")
        if intent == "mail_create":
            draft = self.productivity.mail.create_draft(
                str(slots["recipient"]),
                str(slots.get("subject") or "Wiadomość od JARVIS OS"),
                str(slots.get("body") or "Dzień dobry,\n\nPrzygotowano lokalny szkic wiadomości."),
                priority="NORMAL",
            )
            return (
                f"Przygotowałem lokalny szkic do {draft['recipient']} "
                f"z tematem „{draft['subject']}”. Nic nie wysłałem."
            )
        if intent == "calendar_status":
            return self.productivity.handle("Pokaż status kalendarza")
        if intent == "calendar_conflicts":
            return self.productivity.handle("Sprawdź konflikty kalendarza")
        if intent == "calendar_add":
            when = datetime.fromisoformat(str(slots["when"]))
            event = self.productivity.calendar.add_event(
                str(slots["title"]),
                when,
                duration_minutes=int(slots.get("duration_minutes", 30) or 30),
            )
            return (
                f"Dodałem lokalne spotkanie „{event['title']}” na "
                f"{event['start_at']}. Synchronizacja z chmurą jest wyłączona."
            )
        if intent == "document_search":
            results = self.productivity.documents.search(str(slots["query"]))
            if not results:
                return f"Nie znalazłem lokalnego dokumentu dla „{slots['query']}”."
            return "Znalazłem: " + " | ".join(item["name"] for item in results[:5])
        if intent == "document_scan":
            result = self.productivity.documents.scan()
            return (
                f"Lokalny skan zakończony: {result['scanned']} plików, "
                f"pominięte {result['skipped']}."
            )
        if intent == "reminder_status":
            return self.productivity.handle("Pokaż status przypomnień 2")
        if intent == "reminder_add":
            reminder = self.productivity.reminders.add(
                str(slots["text"]),
                due_at=datetime.fromisoformat(str(slots["when"])),
                recurrence=str(slots.get("recurrence", "NONE")),
            )
            return (
                f"Ustawiłem lokalne przypomnienie „{reminder['text']}” "
                f"na {reminder['due_at']}."
            )
        if intent in {"report_status", "report_review"}:
            return self.productivity.handle("Sprawdź raport produktywności")
        if intent == "report_export":
            report = self.productivity.reporting.export()
            return f"Raport dnia zapisałem lokalnie: {report['text_path']}"
        raise ValueError(f"B123: nieobsługiwana intencja {intent}.")

    def status(self) -> dict[str, Any]:
        value = self.productivity.status()
        return {
            "status": "UNIFIED_PRODUCTIVITY_ROUTER_READY",
            "mail_ready": value["mail"]["status"] == "LOCAL_MAIL_CENTER_READY",
            "calendar_ready": value["calendar"]["status"] == "LOCAL_CALENDAR_READY",
            "documents_ready": value["documents"]["status"] == "LOCAL_DOCUMENT_CENTER_READY",
            "reminders_ready": value["reminders"]["status"] == "REMINDER_CENTER_2_READY",
            "reporting_ready": value["reporting"]["status"] == "DAILY_PRODUCTIVITY_REPORTING_READY",
            "automatic_sending": False,
            "remote_sync": False,
        }

    def _day_overview(self) -> str:
        snapshot = self.productivity.reporting.snapshot()
        return DailyBriefFormatter.format(snapshot)

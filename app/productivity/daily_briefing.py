from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.productivity.calendar_center import LocalCalendarCenter
from app.productivity.document_center import LocalDocumentCenter
from app.productivity.mail_center import LocalMailCenter
from app.productivity.reminder_center import ReminderCenterV2
from app.productivity.common import utc_now


class DailyProductivityBriefing:
    """B110 local daily report and next-day plan assembled from B106-B109."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        mail: LocalMailCenter | None = None,
        calendar: LocalCalendarCenter | None = None,
        documents: LocalDocumentCenter | None = None,
        reminders: ReminderCenterV2 | None = None,
    ) -> None:
        self.root = resolve_project_root(project_root)
        self.mail = mail or LocalMailCenter(self.root)
        self.calendar = calendar or LocalCalendarCenter(self.root)
        self.documents = documents or LocalDocumentCenter(self.root)
        self.reminders = reminders or ReminderCenterV2(self.root)
        self.store = JsonStore(
            self.root / "data" / "productivity" / "daily_briefings.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {"version": "1.0", "reports": [], "updated_at": ""}

    def snapshot(self) -> dict[str, Any]:
        mail = self.mail.status()
        calendar = self.calendar.status()
        documents = self.documents.status()
        reminders = self.reminders.status()
        plan: list[str] = []
        if mail["ready_count"]:
            plan.append(f"Sprawdź {mail['ready_count']} szkiców gotowych do eksportu.")
        if calendar["upcoming_count"]:
            event = dict(calendar.get("next_event", {}) or {})
            plan.append(f"Najbliższe spotkanie: {event.get('title', 'bez nazwy')} — {event.get('start_at', '')}.")
        if reminders["due_count"]:
            plan.append(f"Obsłuż {reminders['due_count']} zaległych przypomnień.")
        if documents["document_count"] == 0:
            plan.append("Uruchom pierwszy lokalny skan dokumentów.")
        if not plan:
            plan.append("Brak pilnych elementów — wybierz najważniejszy cel dnia.")
        return {
            "created_at": utc_now(),
            "mail": mail,
            "calendar": calendar,
            "documents": documents,
            "reminders": reminders,
            "next_day_plan": plan,
            "remote_delivery": False,
        }

    def export(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = self.root / "AI_PLIKI" / "reports"
        directory.mkdir(parents=True, exist_ok=True)
        text_path = directory / f"JARVIS_PRODUCTIVITY_{timestamp}.txt"
        json_path = directory / f"JARVIS_PRODUCTIVITY_{timestamp}.json"
        lines = [
            "JARVIS OS — RAPORT PRODUKTYWNOŚCI B106–B110",
            f"Utworzono: {snapshot['created_at']}",
            "",
            f"B106 szkice: {snapshot['mail']['draft_count']}, gotowe: {snapshot['mail']['ready_count']}, eksporty: {snapshot['mail']['exported_count']}",
            f"B107 wydarzenia: {snapshot['calendar']['event_count']}, konflikty: {snapshot['calendar']['conflict_count']}",
            f"B108 dokumenty: {snapshot['documents']['document_count']}, z treścią: {snapshot['documents']['text_document_count']}",
            f"B109 przypomnienia: {snapshot['reminders']['pending_count']}, pilne: {snapshot['reminders']['due_count']}",
            "",
            "PLAN NA NASTĘPNY DZIEŃ:",
            *[f"- {item}" for item in snapshot["next_day_plan"]],
            "",
            "Bezpieczeństwo: raport lokalny; brak wysyłania do chmury.",
        ]
        text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        data = self._load()
        reports = list(data.get("reports", []) or [])
        record = {"text_path": str(text_path), "json_path": str(json_path), "created_at": snapshot["created_at"]}
        reports.append(record)
        data.update({"reports": reports[-365:], "updated_at": utc_now()})
        self.store.save(data)
        return {"status": "DAILY_PRODUCTIVITY_REPORT_EXPORTED", **record}

    def status(self) -> dict[str, Any]:
        data = self._load()
        reports = list(data.get("reports", []) or [])
        latest = dict(reports[-1] if reports else {})
        preview = self.snapshot()
        return {
            "status": "DAILY_PRODUCTIVITY_REPORTING_READY",
            "report_count": len(reports),
            "latest_report": latest,
            "plan_item_count": len(preview["next_day_plan"]),
            "generated_preview_at": preview["created_at"],
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

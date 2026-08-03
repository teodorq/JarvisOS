from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import clip, utc_now


class OnlineDayCenter:
    """B129 one live overview across Gmail, Calendar, Drive and local reminders."""

    def __init__(self, project_root: str | Path | None, *, gmail: Any, calendar: Any, drive: Any, reminders: Any) -> None:
        self.project_root = resolve_project_root(project_root)
        self.gmail = gmail
        self.calendar = calendar
        self.drive = drive
        self.reminders = reminders
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant" / "day_center.json",
            lambda: {"snapshots": [], "updated_at": ""},
        )

    def snapshot(self) -> dict[str, Any]:
        mail = self.gmail.priority(5)
        events = self.calendar.today()
        reminder_status = self.reminders.status()
        snapshot = {
            "status": "ONLINE_DAY_CENTER_READY",
            "created_at": utc_now(),
            "priority_mail_count": len(mail),
            "priority_mail": mail,
            "today_event_count": len(events),
            "today_events": events,
            "pending_reminders": int(reminder_status.get("pending_count", 0) or 0),
            "next_reminder": dict(reminder_status.get("next_reminder", {}) or {}),
        }
        data = self.store.load()
        if not isinstance(data, dict):
            data = {"snapshots": [], "updated_at": ""}
        snapshots = list(data.get("snapshots", []) or [])
        snapshots.append(snapshot)
        data.update({"snapshots": snapshots[-90:], "updated_at": utc_now()})
        self.store.save(data)
        return snapshot

    def format_snapshot(self, snapshot: dict[str, Any]) -> str:
        mail = list(snapshot.get("priority_mail", []) or [])
        events = list(snapshot.get("today_events", []) or [])
        next_mail = dict(mail[0]) if mail else {}
        next_event = dict(events[0]) if events else {}
        next_reminder = dict(snapshot.get("next_reminder", {}) or {})
        return (
            "B129 CENTRUM DNIA ONLINE\n"
            f"Priorytetowe wiadomości: {snapshot.get('priority_mail_count', 0)}; "
            f"pierwsza: {clip(next_mail.get('subject') or 'brak', 120)}\n"
            f"Dzisiejsze wydarzenia: {snapshot.get('today_event_count', 0)}; "
            f"najbliższe: {clip(next_event.get('title') or 'brak', 120)}\n"
            f"Lokalne przypomnienia: {snapshot.get('pending_reminders', 0)}; "
            f"najbliższe: {clip(next_reminder.get('text') or 'brak', 120)}"
        )

    def status(self) -> dict[str, Any]:
        data = self.store.load()
        snapshots = list(dict(data or {}).get("snapshots", []) or [])
        return {
            "status": "ONLINE_DAY_CENTER_READY",
            "snapshot_count": len(snapshots),
            "latest": dict(snapshots[-1]) if snapshots else {},
            "automatic_polling": False,
        }

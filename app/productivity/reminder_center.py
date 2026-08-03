from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.productivity.common import clean_text, new_id, parse_iso, utc_now


class ReminderCenterV2:
    """B109 local one-time and recurring reminders with explicit completion."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.root / "data" / "productivity" / "reminders_v2.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {"version": "2.0", "reminders": {}, "active_id": "", "updated_at": ""}

    def add(
        self,
        text: str,
        *,
        due_at: str | datetime | None = None,
        minutes: int = 0,
        recurrence: str = "NONE",
    ) -> dict[str, Any]:
        content = clean_text(text, limit=400)
        if not content:
            raise ValueError("Treść przypomnienia jest wymagana.")
        due = due_at if isinstance(due_at, datetime) else parse_iso(due_at)
        if due is None:
            due = datetime.now(timezone.utc) + timedelta(minutes=max(0, min(int(minutes), 525600)))
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        recurrence = str(recurrence).upper().strip()
        if recurrence not in {"NONE", "DAILY", "WEEKLY"}:
            recurrence = "NONE"
        reminder = {
            "reminder_id": new_id("reminder"),
            "text": content,
            "due_at": due.astimezone(timezone.utc).isoformat(),
            "recurrence": recurrence,
            "status": "PENDING",
            "completion_count": 0,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        data = self._load()
        reminders = dict(data.get("reminders", {}) or {})
        reminders[reminder["reminder_id"]] = reminder
        data.update({"reminders": reminders, "active_id": reminder["reminder_id"], "updated_at": utc_now()})
        self.store.save(data)
        return reminder

    def due(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        result = []
        for item in dict(self._load().get("reminders", {}) or {}).values():
            due_at = parse_iso(item.get("due_at"))
            if item.get("status") == "PENDING" and due_at and due_at <= now:
                result.append(dict(item))
        return sorted(result, key=lambda item: str(item.get("due_at", "")))

    def complete(self, reminder_id: str = "") -> dict[str, Any]:
        data = self._load()
        identity = reminder_id or str(data.get("active_id", ""))
        reminder = dict(dict(data.get("reminders", {}) or {}).get(identity, {}) or {})
        if not reminder:
            raise ValueError("Brak aktywnego przypomnienia B109.")
        recurrence = str(reminder.get("recurrence", "NONE"))
        reminder["completion_count"] = int(reminder.get("completion_count", 0)) + 1
        if recurrence in {"DAILY", "WEEKLY"}:
            current = parse_iso(reminder.get("due_at")) or datetime.now(timezone.utc)
            reminder["due_at"] = (current + timedelta(days=1 if recurrence == "DAILY" else 7)).isoformat()
            reminder["status"] = "PENDING"
        else:
            reminder["status"] = "COMPLETED"
            reminder["completed_at"] = utc_now()
        reminder["updated_at"] = utc_now()
        reminders = dict(data.get("reminders", {}) or {})
        reminders[identity] = reminder
        data.update({"reminders": reminders, "active_id": identity, "updated_at": utc_now()})
        self.store.save(data)
        return reminder

    def status(self) -> dict[str, Any]:
        data = self._load()
        reminders = list(dict(data.get("reminders", {}) or {}).values())
        pending = [item for item in reminders if item.get("status") == "PENDING"]
        pending.sort(key=lambda item: str(item.get("due_at", "")))
        return {
            "status": "REMINDER_CENTER_2_READY",
            "reminder_count": len(reminders),
            "pending_count": len(pending),
            "due_count": len(self.due()),
            "completed_count": sum(item.get("status") == "COMPLETED" for item in reminders),
            "recurring_count": sum(item.get("recurrence") in {"DAILY", "WEEKLY"} for item in reminders),
            "next_reminder": pending[0] if pending else {},
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

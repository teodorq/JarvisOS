from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UnifiedContextHub:
    """B122 bounded context shared by text, voice, memory and the active task."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "assistant_v12" / "unified_context.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.2",
            "active_topic": "",
            "last_intent": "",
            "last_command": "",
            "last_response": "",
            "slots": {},
            "pending": {},
            "turns": [],
            "updated_at": "",
        }

    def load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

    def remember(
        self,
        *,
        command: str,
        intent: str,
        response: str,
        slots: dict[str, Any] | None = None,
        source: str = "TEXT",
    ) -> None:
        data = self.load()
        merged = dict(data.get("slots", {}) or {})
        merged.update({key: value for key, value in dict(slots or {}).items() if value not in ("", None)})
        data.update({
            "active_topic": self._topic_for(intent),
            "last_intent": str(intent),
            "last_command": str(command)[:500],
            "last_response": str(response)[:1000],
            "slots": merged,
            "pending": {},
            "updated_at": utc_now(),
        })
        turns = list(data.get("turns", []) or [])
        turns.append({
            "command": str(command)[:500],
            "intent": str(intent),
            "response": str(response)[:1000],
            "slots": dict(slots or {}),
            "source": str(source).upper(),
            "created_at": data["updated_at"],
        })
        data["turns"] = turns[-80:]
        self.store.save(data)

    def set_pending(
        self,
        *,
        intent: str,
        missing: list[str],
        slots: dict[str, Any],
        prompt: str,
    ) -> None:
        data = self.load()
        data["pending"] = {
            "intent": str(intent),
            "missing": list(missing),
            "slots": dict(slots),
            "prompt": str(prompt)[:500],
            "created_at": utc_now(),
        }
        data["active_topic"] = self._topic_for(intent)
        data["updated_at"] = utc_now()
        self.store.save(data)

    def clear_pending(self) -> None:
        data = self.load()
        data["pending"] = {}
        data["updated_at"] = utc_now()
        self.store.save(data)

    def clear(self) -> None:
        self.store.save(self._default())

    def status(self) -> dict[str, Any]:
        data = self.load()
        pending = dict(data.get("pending", {}) or {})
        return {
            "status": "UNIFIED_CONTEXT_HUB_READY",
            "turn_count": len(list(data.get("turns", []) or [])),
            "active_topic": str(data.get("active_topic", "")),
            "last_intent": str(data.get("last_intent", "")),
            "slot_count": len(dict(data.get("slots", {}) or {})),
            "pending_intent": str(pending.get("intent", "")),
            "pending_missing": list(pending.get("missing", []) or []),
            "context_limit": 80,
        }

    @staticmethod
    def _topic_for(intent: str) -> str:
        value = str(intent)
        if value.startswith("mail_"):
            return "MAIL"
        if value.startswith("calendar_"):
            return "CALENDAR"
        if value.startswith("document_"):
            return "DOCUMENTS"
        if value.startswith("reminder_"):
            return "REMINDERS"
        if value.startswith("day_") or value.startswith("report_"):
            return "DAILY_WORK"
        return "ASSISTANT"

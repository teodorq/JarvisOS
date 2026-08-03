from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_utc(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class NaturalActionContext:
    """Bounded multi-turn state, useful references and execution receipts."""

    PENDING_TTL = timedelta(minutes=30)
    EXECUTION_TTL = timedelta(minutes=3)

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "natural_actions" / "context.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "2.0",
            "pending": {},
            "history": [],
            "last_actions": {},
            "references": {},
            "executions": [],
            "updated_at": "",
        }

    def load(self) -> dict[str, Any]:
        value = self.store.load()
        if not isinstance(value, dict):
            return self._default()
        data = self._default()
        data.update(value)
        return data

    def pending(self) -> dict[str, Any]:
        data = self.load()
        pending = dict(data.get("pending", {}) or {})
        created = _as_utc(pending.get("created_at"))
        if pending and created and datetime.now(timezone.utc) - created > self.PENDING_TTL:
            self.clear_pending()
            return {}
        return pending

    def has_pending(self) -> bool:
        return bool(self.pending())

    def set_pending(
        self,
        *,
        intent: str,
        slots: dict[str, Any],
        missing: list[str],
        prompt: str,
    ) -> None:
        data = self.load()
        previous = dict(data.get("pending", {}) or {})
        data["pending"] = {
            "intent": str(intent),
            "slots": dict(slots),
            "missing": list(missing),
            "prompt": str(prompt)[:500],
            "created_at": previous.get("created_at") or utc_now(),
            "updated_at": utc_now(),
        }
        data["updated_at"] = utc_now()
        self.store.save(data)

    def clear_pending(self) -> None:
        data = self.load()
        data["pending"] = {}
        data["updated_at"] = utc_now()
        self.store.save(data)

    def last_action(self, intent: str = "") -> dict[str, Any]:
        actions = dict(self.load().get("last_actions", {}) or {})
        if intent:
            return dict(actions.get(intent, {}) or {})
        ordered = [
            dict(value)
            for value in actions.values()
            if isinstance(value, dict) and value.get("created_at")
        ]
        ordered.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return ordered[0] if ordered else {}

    def reference(self, name: str) -> str:
        references = dict(self.load().get("references", {}) or {})
        return str(references.get(str(name), "") or "")

    def remember_reference(self, name: str, value: object) -> None:
        clean = " ".join(str(value or "").split()).strip()
        if not clean:
            return
        data = self.load()
        references = dict(data.get("references", {}) or {})
        references[str(name)] = clean[:500]
        data["references"] = references
        data["updated_at"] = utc_now()
        self.store.save(data)

    def execution_result(self, fingerprint: str) -> str:
        now = datetime.now(timezone.utc)
        for item in reversed(list(self.load().get("executions", []) or [])):
            if str(item.get("fingerprint", "")) != str(fingerprint):
                continue
            created = _as_utc(item.get("created_at"))
            if created and now - created <= self.EXECUTION_TTL:
                return str(item.get("response", "") or "")
        return ""

    def remember_execution(self, fingerprint: str, response: str) -> None:
        data = self.load()
        now = datetime.now(timezone.utc)
        executions = []
        for item in list(data.get("executions", []) or []):
            created = _as_utc(item.get("created_at"))
            if created and now - created <= timedelta(hours=24):
                executions.append(dict(item))
        executions.append({
            "fingerprint": str(fingerprint),
            "response": str(response)[:500],
            "created_at": utc_now(),
        })
        data["executions"] = executions[-80:]
        data["updated_at"] = utc_now()
        self.store.save(data)

    def forget_execution(self, fingerprint: object) -> None:
        key = str(fingerprint or "").strip()
        if not key:
            return
        data = self.load()
        data["executions"] = [
            dict(item) for item in list(data.get("executions", []) or [])
            if str(item.get("fingerprint", "")) != key
        ]
        data["updated_at"] = utc_now()
        self.store.save(data)

    def remember(self, request: Any, response: str) -> None:
        data = self.load()
        intent = str(getattr(request, "intent", ""))
        slots = dict(getattr(request, "slots", {}) or {})
        item = {
            "intent": intent,
            "command": str(getattr(request, "command", ""))[:500],
            "slots": slots,
            "response": str(response)[:500],
            "created_at": utc_now(),
        }
        history = list(data.get("history", []) or [])
        history.append(item)
        data["history"] = history[-80:]
        actions = dict(data.get("last_actions", {}) or {})
        if intent:
            actions[intent] = item
        data["last_actions"] = actions
        references = dict(data.get("references", {}) or {})
        if intent.startswith(("mail_", "gmail_")):
            for key in ("recipient_ref", "recipient_email", "draft_id"):
                value = str(slots.get(key, "") or "").strip()
                if value:
                    references[key] = value
        if intent.startswith("calendar_"):
            mapping = {
                "event_id": "calendar_event_id",
                "event_title": "calendar_event_title",
                "title": "calendar_event_title",
                "when": "calendar_when",
                "new_when": "calendar_when",
                "end_at": "calendar_end_at",
                "reminder_minutes": "calendar_reminder_minutes",
                "duration_minutes": "calendar_duration_minutes",
            }
            for key, reference_name in mapping.items():
                value = slots.get(key)
                if value not in (None, ""):
                    references[reference_name] = str(value)
        data["references"] = references
        data["updated_at"] = utc_now()
        self.store.save(data)

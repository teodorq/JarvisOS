from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


class ActiveResolutionMemory:
    """Local memory for the current alert, proposal and explicit decisions."""

    def __init__(self, project_root: object) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "active_resolution" / "state.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "last_issue": {},
            "last_suggestion": {},
            "decisions": [],
            "updated_at": "",
        }

    def load(self) -> dict[str, Any]:
        value = self.store.load()
        data = self._default()
        if isinstance(value, dict):
            data.update(value)
        return data

    def remember_issue(self, issue: dict[str, Any]) -> None:
        self._save_field("last_issue", dict(issue))

    def last_issue(self) -> dict[str, Any]:
        return dict(self.load().get("last_issue", {}) or {})

    def remember_suggestion(self, suggestion: dict[str, Any]) -> None:
        self._save_field("last_suggestion", dict(suggestion))

    def last_suggestion(self) -> dict[str, Any]:
        return dict(self.load().get("last_suggestion", {}) or {})

    def clear_suggestion(self) -> None:
        self._save_field("last_suggestion", {})

    def decide(
        self,
        fingerprint: str,
        action: str,
        *,
        until: datetime | None = None,
    ) -> None:
        data = self.load()
        decisions = [
            dict(item) for item in list(data.get("decisions", []) or [])
            if str(item.get("fingerprint", "")) != fingerprint
        ]
        decisions.append({
            "fingerprint": fingerprint,
            "action": action,
            "until": until.isoformat() if until is not None else "",
            "created_at": self._now().isoformat(),
            "delivered_at": "",
        })
        data["decisions"] = decisions[-200:]
        self._save(data)

    def decision(self, fingerprint: str) -> dict[str, Any]:
        decisions = list(self.load().get("decisions", []) or [])
        for item in reversed(decisions):
            if str(item.get("fingerprint", "")) == fingerprint:
                return dict(item)
        return {}

    def mark_delivered(self, fingerprint: str) -> None:
        data = self.load()
        decisions = [dict(item) for item in list(data.get("decisions", []) or [])]
        for item in reversed(decisions):
            if str(item.get("fingerprint", "")) == fingerprint:
                item["delivered_at"] = self._now().isoformat()
                break
        data["decisions"] = decisions
        self._save(data)

    def clear_decision(self, fingerprint: str) -> None:
        value = str(fingerprint or "").strip()
        if not value:
            return
        data = self.load()
        current = list(data.get("decisions", []) or [])
        data["decisions"] = [
            dict(item) for item in current
            if str(item.get("fingerprint", "")) != value
        ]
        if len(data["decisions"]) != len(current):
            self._save(data)

    def _save_field(self, name: str, value: Any) -> None:
        data = self.load()
        data[name] = value
        self._save(data)

    def _save(self, data: dict[str, Any]) -> None:
        data["updated_at"] = self._now().isoformat()
        self.store.save(data)

    @staticmethod
    def _now() -> datetime:
        return datetime.now().astimezone().replace(microsecond=0)

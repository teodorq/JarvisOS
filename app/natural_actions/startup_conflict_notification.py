from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.natural_actions.active_resolution_memory import ActiveResolutionMemory
from app.natural_actions.proactive_day import ProactiveDayAnalyzer


class StartupConflictNotificationPolicy:
    """Shows startup conflict alerts only when the conflict is new or changed."""

    def __init__(self, project_root: object) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "startup_conflicts" / "notification_state.json",
            self._default,
        )
        self.active_memory = ActiveResolutionMemory(root)

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "active_fingerprint": "",
            "last_shown_at": "",
            "last_cleared_at": "",
            "show_count": 0,
        }

    @classmethod
    def conflict_fingerprint(cls, events: list[dict[str, Any]]) -> str:
        rows: list[tuple[datetime, datetime, dict[str, str]]] = []
        for raw in events:
            item = dict(raw)
            start = ProactiveDayAnalyzer._dt(item.get("start_at"))
            if start is None:
                continue
            end = ProactiveDayAnalyzer._dt(item.get("end_at"))
            if end is None:
                continue
            rows.append((start, end, {
                "id": str(item.get("id", "")),
                "title": str(item.get("title", "")),
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
            }))
        rows.sort(key=lambda row: (row[0], row[1], row[2]["id"]))
        pairs: list[dict[str, str]] = []
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                if right[0] >= left[1]:
                    break
                if left[0] < right[1] and right[0] < left[1]:
                    pairs.append({
                        "first_id": left[2]["id"],
                        "first_title": left[2]["title"],
                        "first_start": left[2]["start_at"],
                        "first_end": left[2]["end_at"],
                        "second_id": right[2]["id"],
                        "second_title": right[2]["title"],
                        "second_start": right[2]["start_at"],
                        "second_end": right[2]["end_at"],
                    })
        if not pairs:
            return ""
        raw = json.dumps(pairs, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def filter(self, result: dict[str, Any]) -> dict[str, Any]:
        filtered = dict(result or {})
        if not filtered.get("scan_completed"):
            return filtered
        state = self._load()
        fingerprint = str(filtered.get("fingerprint", "") or "")
        conflict_present = bool(filtered.get("conflict_count")) and bool(fingerprint)
        if not conflict_present:
            if state.get("active_fingerprint"):
                state["active_fingerprint"] = ""
                state["last_cleared_at"] = self._now()
                self.store.save(state)
            filtered["notification_reason"] = "quiet"
            return filtered
        if not filtered.get("should_show"):
            filtered["notification_reason"] = "suppressed_by_decision"
            return filtered
        same = str(state.get("active_fingerprint", "")) == fingerprint
        if same and not filtered.get("reactivated_after_undo"):
            filtered["should_show"] = False
            filtered["duplicate_suppressed"] = True
            filtered["notification_reason"] = "unchanged"
            return filtered
        state.update({
            "active_fingerprint": fingerprint,
            "last_shown_at": self._now(),
            "show_count": int(state.get("show_count", 0) or 0) + 1,
        })
        self.store.save(state)
        context = dict(filtered.get("conflict_context", {}) or {})
        if context:
            self.active_memory.remember_issue(context)
        filtered["duplicate_suppressed"] = False
        filtered["notification_reason"] = "changed" if same else "new"
        return filtered

    def status(self) -> dict[str, Any]:
        state = self._load()
        return {
            "status": "NEW_CHANGED_CONFLICT_NOTIFICATION_READY",
            "active_fingerprint": str(state.get("active_fingerprint", "")),
            "show_count": int(state.get("show_count", 0) or 0),
            "duplicate_notifications_suppressed": True,
            "automatic_writes": False,
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        data = self._default()
        if isinstance(value, dict):
            data.update(value)
        return data

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().replace(microsecond=0).isoformat()

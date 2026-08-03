from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from app.assistant.natural_language import fold_text
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import utc_now
from app.online_assistant.google_workspace import GoogleWorkspaceProvider


class GoogleCalendarCenter:
    """B127 live Google Calendar overview, conflicts and confirmed writes."""

    def __init__(self, project_root: str | Path | None = None, *, provider: Any | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider or GoogleWorkspaceProvider(self.project_root)
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant" / "calendar_history.json",
            lambda: {"operations": [], "updated_at": ""},
        )

    def today(self) -> list[dict[str, Any]]:
        now = datetime.now().astimezone()
        start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        end = start + timedelta(days=1)
        events = self.provider.list_calendar_events(start_at=start, end_at=end)
        self._record("READ_TODAY", {"count": len(events)})
        return events

    def upcoming(self, days: int = 7) -> list[dict[str, Any]]:
        start = datetime.now().astimezone()
        end = start + timedelta(days=max(1, min(int(days), 30)))
        events = self.provider.list_calendar_events(start_at=start, end_at=end)
        self._record("READ_UPCOMING", {"count": len(events), "days": days})
        return events

    def conflicts(self) -> list[dict[str, Any]]:
        events = self.upcoming(7)
        normalized: list[tuple[datetime, datetime, dict[str, Any]]] = []
        for item in events:
            try:
                start = datetime.fromisoformat(str(item.get("start_at", "")).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(item.get("end_at", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            normalized.append((start, end, item))
        normalized.sort(key=lambda row: row[0])
        conflicts: list[dict[str, Any]] = []
        for left_index, (left_start, left_end, left) in enumerate(normalized):
            for right_start, right_end, right in normalized[left_index + 1 :]:
                if right_start >= left_end:
                    break
                if left_start < right_end and right_start < left_end:
                    conflicts.append({
                        "left": left,
                        "right": right,
                        "overlap_start": max(left_start, right_start).isoformat(),
                        "overlap_end": min(left_end, right_end).isoformat(),
                    })
        self._record("CHECK_CONFLICTS", {"count": len(conflicts)})
        return conflicts

    def create_event(
        self,
        title: str,
        start_at: datetime,
        *,
        duration_minutes: int = 30,
        description: str = "",
        reminder_minutes: int | None = None,
    ) -> dict[str, Any]:
        kwargs = {
            "title": title,
            "start_at": start_at,
            "duration_minutes": duration_minutes,
            "description": description,
        }
        if reminder_minutes is not None:
            kwargs["reminder_minutes"] = reminder_minutes
        result = self.provider.create_calendar_event(**kwargs)
        self._record(
            "CREATE_EVENT",
            {"event_id": result.get("event_id", ""), "title": title},
        )
        return result


    def find_events(
        self,
        query: str,
        *,
        start_at: datetime,
        end_at: datetime,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        events = self.provider.list_calendar_events(
            start_at=start_at, end_at=end_at, max_results=max_results
        )
        words = [word.strip(" ,.-?!") for word in fold_text(query).split() if len(word) > 2]
        if not words:
            matches = list(events)
        else:
            scored = []
            for event in events:
                title = fold_text(event.get("title", ""))
                score = sum(
                    word in title or (len(word) >= 5 and word[:5] in title)
                    for word in words
                )
                if score:
                    scored.append((score, str(event.get("start_at", "")), event))
            scored.sort(key=lambda row: (-row[0], row[1]))
            matches = [dict(row[2]) for row in scored]
        self._record("FIND_EVENTS", {"query": query, "count": len(matches)})
        return matches[:max_results]

    def update_event(
        self,
        event_id: str,
        title: str,
        start_at: datetime,
        *,
        duration_minutes: int = 60,
        reminder_minutes: int | None = None,
    ) -> dict[str, Any]:
        result = self.provider.update_calendar_event(
            event_id, title=title, start_at=start_at,
            duration_minutes=duration_minutes, reminder_minutes=reminder_minutes,
        )
        self._record("UPDATE_EVENT", {"event_id": event_id, "title": title})
        return result

    def delete_event(self, event_id: str, title: str = "") -> dict[str, Any]:
        result = self.provider.delete_calendar_event(event_id)
        self._record("DELETE_EVENT", {"event_id": event_id, "title": title})
        return result

    def status(self) -> dict[str, Any]:
        data = self.store.load()
        operations = list(dict(data or {}).get("operations", []) or [])
        connected = bool(self.provider.connection_status()["token_present"])
        return {
            "status": "REAL_GOOGLE_CALENDAR_READY" if connected else "REAL_GOOGLE_CALENDAR_AWAITING_CONNECTION",
            "connected": connected,
            "operation_count": len(operations),
            "last_operation": dict(operations[-1]) if operations else {},
            "writes_require_confirmation": True,
        }

    def _record(self, action: str, details: dict[str, Any]) -> None:
        data = self.store.load()
        if not isinstance(data, dict):
            data = {"operations": [], "updated_at": ""}
        operations = list(data.get("operations", []) or [])
        operations.append({"action": action, "details": details, "created_at": utc_now()})
        data.update({"operations": operations[-200:], "updated_at": utc_now()})
        self.store.save(data)

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.productivity.common import clean_text, new_id, parse_iso, utc_now


class LocalCalendarCenter:
    """B107 persistent local calendar with deterministic conflict detection."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.root / "data" / "productivity" / "calendar.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {"version": "1.0", "events": {}, "updated_at": ""}

    def add_event(
        self,
        title: str,
        start_at: str | datetime,
        *,
        duration_minutes: int = 30,
        location: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        clean_title = clean_text(title, limit=180)
        start = start_at if isinstance(start_at, datetime) else parse_iso(start_at)
        if not clean_title or start is None:
            raise ValueError("Nazwa i poprawna data spotkania są wymagane.")
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        duration = max(5, min(int(duration_minutes), 1440))
        end = start.astimezone(timezone.utc) + timedelta(minutes=duration)
        event = {
            "event_id": new_id("event"),
            "title": clean_title,
            "start_at": start.astimezone(timezone.utc).isoformat(),
            "end_at": end.isoformat(),
            "duration_minutes": duration,
            "location": clean_text(location, limit=300),
            "notes": str(notes).strip()[:4000],
            "status": "SCHEDULED",
            "created_at": utc_now(),
        }
        data = self._load()
        events = dict(data.get("events", {}) or {})
        events[event["event_id"]] = event
        data.update({"events": events, "updated_at": utc_now()})
        self.store.save(data)
        return event

    def add_demo(self) -> dict[str, Any]:
        tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
        start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, tzinfo=timezone.utc)
        data = self._load()
        for event in dict(data.get("events", {}) or {}).values():
            if event.get("title") == "Plan dnia JARVIS" and event.get("start_at") == start.isoformat():
                return dict(event)
        return self.add_event("Plan dnia JARVIS", start, duration_minutes=45, location="Lokalnie")

    def conflicts(self) -> list[dict[str, Any]]:
        events = [
            dict(item)
            for item in dict(self._load().get("events", {}) or {}).values()
            if item.get("status") == "SCHEDULED"
        ]
        events.sort(key=lambda item: str(item.get("start_at", "")))
        result: list[dict[str, Any]] = []
        for index, first in enumerate(events):
            first_start = parse_iso(first.get("start_at"))
            first_end = parse_iso(first.get("end_at"))
            if not first_start or not first_end:
                continue
            for second in events[index + 1:]:
                second_start = parse_iso(second.get("start_at"))
                second_end = parse_iso(second.get("end_at"))
                if not second_start or not second_end:
                    continue
                if second_start >= first_end:
                    break
                if first_start < second_end and second_start < first_end:
                    result.append({"first": first, "second": second})
        return result

    def upcoming(self, *, days: int = 14) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=max(1, min(int(days), 365)))
        events = []
        for item in dict(self._load().get("events", {}) or {}).values():
            start = parse_iso(item.get("start_at"))
            if item.get("status") == "SCHEDULED" and start and now <= start <= end:
                events.append(dict(item))
        return sorted(events, key=lambda item: str(item.get("start_at", "")))

    def status(self) -> dict[str, Any]:
        data = self._load()
        events = list(dict(data.get("events", {}) or {}).values())
        upcoming = self.upcoming()
        conflicts = self.conflicts()
        return {
            "status": "LOCAL_CALENDAR_READY",
            "event_count": len(events),
            "upcoming_count": len(upcoming),
            "conflict_count": len(conflicts),
            "next_event": upcoming[0] if upcoming else {},
            "timezone": "UTC",
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

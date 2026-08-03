from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import clip, utc_now


class CalendarIntelligenceService:
    """B133 week analysis, conflicts and bounded free-slot suggestions."""

    def __init__(self, project_root: str | Path | None = None, *, provider: Any, reliability: Any) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider
        self.reliability = reliability
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant_v13" / "calendar_intelligence.json",
            lambda: {"analyses": [], "operations": [], "updated_at": ""},
        )

    def week(self, days: int = 7) -> dict[str, Any]:
        days = max(1, min(int(days), 14))
        start = datetime.now().astimezone()
        end = start + timedelta(days=days)
        read = self.reliability.read(
            f"calendar_week_{days}",
            lambda: self.provider.list_calendar_events(
                start_at=start, end_at=end, max_results=50
            ),
        )
        events = self._normalized(list(read["value"] or []))
        conflicts = self._conflicts(events)
        result = {
            "status": "CALENDAR_INTELLIGENCE_READY",
            "mode": read["mode"], "days": days, "event_count": len(events),
            "events": [row[2] for row in events], "conflicts": conflicts,
            "conflict_count": len(conflicts),
        }
        self._record_analysis(result)
        return result

    def suggest_slots(
        self,
        *,
        duration_minutes: int = 30,
        days: int = 7,
        limit: int = 5,
    ) -> dict[str, Any]:
        duration = max(15, min(int(duration_minutes), 240))
        analysis = self.week(days)
        events = self._normalized(list(analysis["events"] or []))
        now = datetime.now().astimezone()
        slots: list[dict[str, str]] = []
        for offset in range(max(1, min(int(days), 14))):
            day = now.date() + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            cursor = datetime.combine(day, time(8, 0), tzinfo=now.tzinfo)
            end_of_day = datetime.combine(day, time(17, 0), tzinfo=now.tzinfo)
            if cursor < now:
                minutes = ((now.minute + 14) // 15) * 15
                cursor = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minutes)
            while cursor + timedelta(minutes=duration) <= end_of_day:
                end = cursor + timedelta(minutes=duration)
                if not any(cursor < event_end and event_start < end for event_start, event_end, _ in events):
                    slots.append({"start_at": cursor.isoformat(), "end_at": end.isoformat()})
                    if len(slots) >= max(1, min(int(limit), 10)):
                        self._record("SUGGEST_SLOTS", {"count": len(slots), "duration": duration})
                        return {"status": "CALENDAR_SLOTS_READY", "duration_minutes": duration, "slots": slots}
                cursor += timedelta(minutes=30)
        self._record("SUGGEST_SLOTS", {"count": len(slots), "duration": duration})
        return {"status": "CALENDAR_SLOTS_READY", "duration_minutes": duration, "slots": slots}

    def create_event(self, title: str, start_at: datetime, duration_minutes: int = 30) -> dict[str, Any]:
        result = self.reliability.write(
            "calendar_create_event",
            lambda: self.provider.create_calendar_event(
                title=title, start_at=start_at,
                duration_minutes=duration_minutes, description="Utworzone przez JARVIS OS",
            ),
        )
        self._record("CREATE_EVENT", {"event_id": result.get("event_id", ""), "title": clip(title, 200)})
        return result

    def status(self) -> dict[str, Any]:
        data = self._load()
        analyses = list(data.get("analyses", []) or [])
        operations = list(data.get("operations", []) or [])
        latest = dict(analyses[-1]) if analyses else {}
        return {
            "status": "CALENDAR_INTELLIGENCE_READY",
            "analysis_count": len(analyses),
            "operation_count": len(operations),
            "latest_event_count": int(latest.get("event_count", 0) or 0),
            "latest_conflict_count": int(latest.get("conflict_count", 0) or 0),
            "writes_require_confirmation": True,
        }

    @staticmethod
    def _normalized(events: list[dict[str, Any]]) -> list[tuple[datetime, datetime, dict[str, Any]]]:
        result: list[tuple[datetime, datetime, dict[str, Any]]] = []
        for raw in events:
            item = dict(raw or {})
            try:
                start = datetime.fromisoformat(str(item.get("start_at", "")).replace("Z", "+00:00"))
                end = datetime.fromisoformat(str(item.get("end_at", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if start.tzinfo is None:
                start = start.astimezone()
            if end.tzinfo is None:
                end = end.astimezone()
            result.append((start.astimezone(), end.astimezone(), item))
        result.sort(key=lambda row: row[0])
        return result

    @staticmethod
    def _conflicts(events: list[tuple[datetime, datetime, dict[str, Any]]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for index, (left_start, left_end, left) in enumerate(events):
            for right_start, right_end, right in events[index + 1:]:
                if right_start >= left_end:
                    break
                if left_start < right_end and right_start < left_end:
                    result.append({
                        "left": left, "right": right,
                        "overlap_start": max(left_start, right_start).isoformat(),
                        "overlap_end": min(left_end, right_end).isoformat(),
                    })
        return result

    def _record_analysis(self, result: dict[str, Any]) -> None:
        data = self._load()
        analyses = list(data.get("analyses", []) or [])
        analyses.append({
            "created_at": utc_now(), "mode": result["mode"],
            "event_count": result["event_count"], "conflict_count": result["conflict_count"],
        })
        data.update({"analyses": analyses[-100:], "updated_at": utc_now()})
        self.store.save(data)

    def _record(self, action: str, details: dict[str, Any]) -> None:
        data = self._load()
        operations = list(data.get("operations", []) or [])
        operations.append({"action": action, "details": details, "created_at": utc_now()})
        data.update({"operations": operations[-200:], "updated_at": utc_now()})
        self.store.save(data)

    def _load(self) -> dict[str, Any]:
        data = self.store.load()
        return data if isinstance(data, dict) else {"analyses": [], "operations": [], "updated_at": ""}

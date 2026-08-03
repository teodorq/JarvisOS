from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Callable

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.natural_actions.day_quality import IntelligentDayQuality


class ProactiveDayAnalyzer:
    """B161-B165 conservative urgency, conflict and next-step analysis."""

    @classmethod
    def analyze(cls, snapshot: dict[str, Any]) -> dict[str, Any]:
        now = cls._dt(snapshot.get("now")) or datetime.now().astimezone()
        events = [dict(item) for item in list(snapshot.get("events", []) or [])]
        events.sort(key=lambda item: str(item.get("start_at", "")))
        conflicts = cls.conflicts(events)
        reminders = dict(snapshot.get("reminders", {}) or {})
        mail = list(snapshot.get("mail", []) or [])
        due = cls._count(reminders.get("due_count"))
        next_event = cls._next_event(events, now)
        minutes = cls._minutes_until(next_event.get("start_at"), now) if next_event else None
        level = "quiet"
        if conflicts or due:
            level = "critical"
        elif minutes is not None and 0 <= minutes <= 90:
            level = "high"
        elif mail or next_event:
            level = "normal"
        next_action = cls.next_action(snapshot)
        return {
            "level": level,
            "conflicts": conflicts,
            "due_reminders": due,
            "next_event": next_event,
            "minutes_to_event": minutes,
            "mail": mail[:3],
            "next_action": next_action,
            "has_attention": level != "quiet",
        }

    @classmethod
    def conflicts(cls, events: list[dict[str, Any]]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        normalized: list[tuple[datetime, datetime, str]] = []
        for event in events:
            start = cls._dt(event.get("start_at"))
            if start is None:
                continue
            end = cls._dt(event.get("end_at")) or start + timedelta(hours=1)
            title = cls._clean(event.get("title")) or "wydarzenie"
            normalized.append((start, end, title))
        normalized.sort(key=lambda item: item[0])
        for index, first in enumerate(normalized):
            for second in normalized[index + 1:]:
                if second[0] >= first[1]:
                    break
                if second[0] < first[1] and second[1] > first[0]:
                    result.append({
                        "first": first[2],
                        "second": second[2],
                        "at": max(first[0], second[0]).astimezone().strftime("%H:%M"),
                    })
        return result[:4]

    @classmethod
    def next_action(cls, snapshot: dict[str, Any]) -> str:
        reminders = dict(snapshot.get("reminders", {}) or {})
        next_reminder = dict(reminders.get("next_reminder", {}) or {})
        reminder_text = cls._clean(next_reminder.get("text"))
        if cls._count(reminders.get("due_count")) and reminder_text:
            return f"„{reminder_text}”"
        conflicts = cls.conflicts(list(snapshot.get("events", []) or []))
        if conflicts:
            item = conflicts[0]
            return (
                f"„Rozwiąż konflikt między {item['first']} i "
                f"{item['second']} o {item['at']}”"
            )
        now = cls._dt(snapshot.get("now")) or datetime.now().astimezone()
        event = cls._next_event(list(snapshot.get("events", []) or []), now)
        if event:
            title = cls._clean(event.get("title")) or "wydarzenia"
            return f"„Przygotuj się do {title} {cls._moment(event.get('start_at'))}”"
        mail = list(snapshot.get("mail", []) or [])
        if mail:
            subject = cls._clean(mail[0].get("subject")) or "ważną wiadomość"
            return f"„Sprawdź wiadomość {subject}”"
        if reminder_text:
            return f"„{reminder_text}”"
        return ""

    @classmethod
    def compose(cls, snapshot: dict[str, Any], analysis: dict[str, Any]) -> str:
        parts: list[str] = []
        conflicts = list(analysis.get("conflicts", []) or [])
        if conflicts:
            item = conflicts[0]
            parts.append(
                f"Masz konflikt: „{item['first']}” i „{item['second']}” "
                f"nakładają się o {item['at']}."
            )
        due = cls._count(analysis.get("due_reminders"))
        if due:
            parts.append("Masz " + IntelligentDayQuality.reminder_count(due) + ".")
        event = dict(analysis.get("next_event", {}) or {})
        minutes = analysis.get("minutes_to_event")
        if event and isinstance(minutes, int) and 0 <= minutes <= 180:
            title = cls._clean(event.get("title")) or "wydarzenie"
            if minutes < 60:
                parts.append(f"„{title}” zaczyna się za {max(0, minutes)} min.")
            else:
                parts.append(f"„{title}” zaczyna się o {cls._clock(event.get('start_at'))}.")
        mail = list(analysis.get("mail", []) or [])
        if mail:
            subject = cls._clean(mail[0].get("subject")) or "wiadomość"
            next_action = str(analysis.get("next_action", "") or "")
            if subject not in next_action:
                parts.append(f"Do sprawdzenia: „{subject}”.")
        next_action = str(analysis.get("next_action", "") or "")
        if next_action:
            parts.append(f"Najlepszy następny krok: {next_action}.")
        if not parts:
            parts.append("Dzień wygląda spokojnie. Nie widzę pilnej sprawy.")
        now = cls._dt(snapshot.get("now")) or datetime.now().astimezone()
        heading = "Poranny brief" if 5 <= now.hour < 12 else "Brief dnia"
        return heading + ": " + " ".join(parts)

    @staticmethod
    def fingerprint(analysis: dict[str, Any]) -> str:
        raw = json.dumps(analysis, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    @classmethod
    def _next_event(
        cls,
        events: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        future = []
        for raw in events:
            event = dict(raw)
            start = cls._dt(event.get("start_at"))
            end = cls._dt(event.get("end_at")) or (
                start + timedelta(hours=1) if start else None
            )
            if start and end and end >= now:
                future.append((start, event))
        future.sort(key=lambda item: item[0])
        return future[0][1] if future else {}

    @classmethod
    def _minutes_until(cls, value: object, now: datetime) -> int | None:
        parsed = cls._dt(value)
        if parsed is None:
            return None
        return int((parsed - now).total_seconds() // 60)

    @classmethod
    def _moment(cls, value: object) -> str:
        parsed = cls._dt(value)
        return parsed.astimezone().strftime("o %H:%M") if parsed else "wkrótce"

    @classmethod
    def _clock(cls, value: object) -> str:
        parsed = cls._dt(value)
        return parsed.astimezone().strftime("%H:%M") if parsed else "nieznanej porze"

    @staticmethod
    def _dt(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value.astimezone()
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _clean(value: object) -> str:
        return IntelligentDayQuality.clean_text(value, 240)

    @staticmethod
    def _count(value: object) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

class ProactiveDayService:
    """Shows one useful daily brief and suppresses duplicate notifications."""

    REPEAT_AFTER = timedelta(hours=4)

    def __init__(
        self,
        project_root: object,
        snapshot_provider: Callable[[int], dict[str, Any]],
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        root = resolve_project_root(project_root)
        self.snapshot_provider = snapshot_provider
        self.now_provider = now_provider or (lambda: datetime.now().astimezone())
        self.store = JsonStore(
            root / "data" / "proactive_day" / "state.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "last_day": "",
            "last_fingerprint": "",
            "last_shown_at": "",
            "last_level": "",
            "last_conflict_count": 0,
            "show_count": 0,
        }

    def startup_brief(self, *, force: bool = False) -> dict[str, Any]:
        snapshot = dict(self.snapshot_provider(0) or {})
        tomorrow = dict(self.snapshot_provider(1) or {})
        merged = list(snapshot.get("events", []) or []) + list(
            tomorrow.get("events", []) or []
        )
        snapshot["events"] = list({
            (
                str(item.get("id", "")), str(item.get("title", "")),
                str(item.get("start_at", "")), str(item.get("end_at", "")),
            ): dict(item) for item in merged
        }.values())
        analysis = ProactiveDayAnalyzer.analyze(snapshot)
        fingerprint = ProactiveDayAnalyzer.fingerprint(analysis)
        now = self.now_provider().astimezone()
        state = self._load()
        same_day = str(state.get("last_day", "")) == now.date().isoformat()
        same_fingerprint = state.get("last_fingerprint") == fingerprint
        repeat_ready = self._repeat_ready(state.get("last_shown_at"), now)
        changed_critical = (
            analysis["level"] == "critical"
            and (not same_fingerprint or repeat_ready)
        )
        should_show = force or not same_day or changed_critical
        message = ProactiveDayAnalyzer.compose(snapshot, analysis)
        if should_show:
            state.update({
                "last_day": now.date().isoformat(),
                "last_fingerprint": fingerprint,
                "last_shown_at": now.isoformat(),
                "last_level": analysis["level"],
                "last_conflict_count": len(analysis["conflicts"]),
                "show_count": int(state.get("show_count", 0) or 0) + 1,
            })
            self.store.save(state)
        return {
            "should_show": should_show,
            "message": message,
            "level": analysis["level"],
            "speak": (
                analysis["level"] in {"high", "critical"}
                and 7 <= now.hour < 22
            ),
            "next_action": analysis["next_action"],
            "conflict_count": len(analysis["conflicts"]),
            "fingerprint": fingerprint,
        }

    def status(self) -> dict[str, Any]:
        state = self._load()
        return {
            "status": "PROACTIVE_DAY_READY",
            "last_day": str(state.get("last_day", "")),
            "show_count": int(state.get("show_count", 0) or 0),
            "automatic_writes": False,
            "duplicate_notifications_suppressed": True,
            "quiet_hours": "22:00-07:00",
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        data = self._default()
        if isinstance(value, dict):
            data.update(value)
        return data

    @classmethod
    def _repeat_ready(cls, value: object, now: datetime) -> bool:
        try:
            previous = datetime.fromisoformat(str(value)).astimezone()
        except (TypeError, ValueError, OSError):
            return True
        return now - previous >= cls.REPEAT_AFTER

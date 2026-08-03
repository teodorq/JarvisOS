from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from typing import Any


class ActiveIssueAnalyzer:
    """Builds actionable conflict, reminder and priority-mail issue records."""

    def __init__(self, daily: Any) -> None:
        self.daily = daily

    def snapshot(self) -> dict[str, Any]:
        today = dict(self.daily._snapshot(0) or {})
        tomorrow = dict(self.daily._snapshot(1) or {})
        events = list(today.get("events", []) or []) + list(
            tomorrow.get("events", []) or []
        )
        today["events"] = list({
            (
                str(item.get("id", "")), str(item.get("title", "")),
                str(item.get("start_at", "")), str(item.get("end_at", "")),
            ): dict(item)
            for item in events
        }.values())
        return today

    def current_issue(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        conflicts = self.conflicts(list(snapshot.get("events", []) or []))
        if conflicts:
            return self.with_fingerprint({"type": "conflict", **conflicts[0]})
        reminders = dict(snapshot.get("reminders", {}) or {})
        if self.count(reminders.get("due_count")):
            reminder = dict(reminders.get("next_reminder", {}) or {})
            return self.with_fingerprint({
                "type": "reminder",
                "text": self.clean(reminder.get("text")) or "pilne przypomnienie",
                "due_at": str(reminder.get("due_at", "")),
            })
        mail = list(snapshot.get("mail", []) or [])
        return self.mail_issue(mail[0]) if mail else {}

    def conflict_issue(self) -> dict[str, Any]:
        conflicts = self.conflicts(list(self.snapshot().get("events", []) or []))
        return self.with_fingerprint(
            {"type": "conflict", **conflicts[0]}
        ) if conflicts else {}

    def top_mail_issue(self) -> dict[str, Any]:
        mail = list(self.snapshot().get("mail", []) or [])
        return self.mail_issue(mail[0]) if mail else {}

    def mail_issue(self, raw: dict[str, Any]) -> dict[str, Any]:
        item = dict(raw or {})
        return self.with_fingerprint({
            "type": "mail",
            "message_id": str(item.get("id", "")),
            "thread_id": str(item.get("thread_id", "")),
            "from": self.clean(item.get("from")),
            "subject": self.clean(item.get("subject")) or "wiadomość",
            "snippet": self.clean(item.get("snippet")),
        })

    def conflicts(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for event in events:
            start = self.dt(event.get("start_at"))
            if start is None:
                continue
            end = self.dt(event.get("end_at")) or start + timedelta(hours=1)
            rows.append({
                "id": str(event.get("id", "")),
                "title": self.clean(event.get("title")) or "wydarzenie",
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
            })
        rows.sort(key=lambda item: str(item["start_at"]))
        result: list[dict[str, Any]] = []
        for index, first in enumerate(rows):
            first_start, first_end = self.dt(first["start_at"]), self.dt(first["end_at"])
            for second in rows[index + 1:]:
                second_start, second_end = self.dt(second["start_at"]), self.dt(second["end_at"])
                if None in {first_start, first_end, second_start, second_end}:
                    continue
                if second_start >= first_end:
                    break
                if second_end > first_start:
                    result.append({
                        "first": first,
                        "second": second,
                        "at": max(first_start, second_start).strftime("%H:%M"),
                    })
        return result

    def conflict_suggestion(self, issue: dict[str, Any]) -> dict[str, Any]:
        first, second = dict(issue["first"]), dict(issue["second"])
        first_end = self.dt(first.get("end_at"))
        second_start = self.dt(second.get("start_at"))
        second_end = self.dt(second.get("end_at"))
        if None in {first_end, second_start, second_end}:
            raise ValueError("Nie udało się odczytać godzin konfliktu.")
        duration = max(5, int((second_end - second_start).total_seconds() // 60))
        new_when = self.next_free_start(
            self.snapshot().get("events", []),
            str(second.get("id", "")),
            first_end,
            duration,
        )
        return {
            "kind": "calendar_move",
            "issue_fingerprint": issue["fingerprint"],
            "event_id": second.get("id", ""),
            "event_title": second.get("title", "wydarzenie"),
            "event_start": second.get("start_at", ""),
            "event_end": second.get("end_at", ""),
            "new_when": new_when.isoformat(),
            "duration_minutes": duration,
        }

    def event_slots(
        self,
        event: dict[str, Any],
        issue: dict[str, Any],
    ) -> dict[str, Any]:
        start, end = self.dt(event.get("start_at")), self.dt(event.get("end_at"))
        duration = int((end - start).total_seconds() // 60) if start and end else 60
        return {
            "kind": "calendar_move",
            "issue_fingerprint": issue.get("fingerprint", ""),
            "event_id": event.get("id", ""),
            "event_title": event.get("title", "wydarzenie"),
            "event_start": event.get("start_at", ""),
            "event_end": event.get("end_at", ""),
            "duration_minutes": duration,
        }

    def next_free_start(
        self,
        events: list[dict[str, Any]],
        moving_id: str,
        candidate: datetime,
        duration: int,
    ) -> datetime:
        occupied = []
        for event in events:
            if str(event.get("id", "")) == moving_id:
                continue
            start, end = self.dt(event.get("start_at")), self.dt(event.get("end_at"))
            if start is not None and end is not None:
                occupied.append((start, end))
        occupied.sort(key=lambda item: item[0])
        while True:
            target_end = candidate + timedelta(minutes=duration)
            overlap = next(
                ((start, end) for start, end in occupied
                 if candidate < end and target_end > start),
                None,
            )
            if overlap is None:
                return candidate
            candidate = overlap[1]

    @staticmethod
    def with_fingerprint(issue: dict[str, Any]) -> dict[str, Any]:
        payload = dict(issue)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        payload["fingerprint"] = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:24]
        return payload

    @staticmethod
    def dt(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value.astimezone()
        try:
            return datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).astimezone()
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def clean(value: object) -> str:
        return " ".join(str(value or "").split()).strip(" ,.-")[:500]

    @staticmethod
    def count(value: object) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

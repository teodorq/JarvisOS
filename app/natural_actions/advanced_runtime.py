from __future__ import annotations

from datetime import datetime
from typing import Any

from app.natural_actions.models import NaturalActionRequest


class AdvancedNaturalActionRuntime:
    """Execution for B151-B155 calendar mutations and existing drafts."""

    INTENTS = {
        "mail_send_existing",
        "calendar_search",
        "calendar_update",
        "calendar_delete",
    }

    def __init__(self, online: Any, formatter: Any) -> None:
        self.online = online
        self.formatter = formatter

    def execute(self, request: NaturalActionRequest) -> str:
        slots = request.slots
        if request.intent == "mail_send_existing":
            live = getattr(self.online, "gmail_live", None)
            if live is not None:
                live.send_draft_verified(slots["draft_id"])
            else:
                self.online.gmail.send_draft(slots["draft_id"])
            return f"Ostatni szkic do {slots['recipient_ref']} został wysłany i sprawdzony w Gmail."
        if request.intent == "calendar_search":
            return self._format_search(slots)
        if request.intent == "calendar_update":
            return self._update(slots)
        if request.intent == "calendar_delete":
            self.online.calendar.delete_event(
                slots["event_id"], title=slots.get("event_title", "")
            )
            return f"Usunąłem „{slots['event_title']}” z kalendarza."
        raise ValueError("Nie mam bezpiecznego wykonawcy dla tego celu.")

    def _update(self, slots: dict[str, Any]) -> str:
        new_when = self._parse(slots["new_when"])
        result = self.online.calendar.update_event(
            slots["event_id"],
            slots["event_title"],
            new_when,
            duration_minutes=self._duration(slots),
            reminder_minutes=slots.get("new_reminder_minutes"),
        )
        slots["when"] = str(result.get("start_at", new_when.isoformat()))
        slots["end_at"] = str(result.get("end_at", ""))
        return f"Przeniosłem „{slots['event_title']}” na {self.formatter.when(new_when)}."

    def _format_search(self, slots: dict[str, Any]) -> str:
        matches = list(slots.get("matches", []) or [])
        if not matches:
            return "Nie znalazłem pasujących wydarzeń w kalendarzu."
        lines = [
            f"{item.get('title', 'wydarzenie')} — "
            f"{self.formatter.when(self._parse(item.get('start_at')))}"
            for item in matches[:5]
        ]
        return "Znalazłem: " + "; ".join(lines) + "."

    @classmethod
    def _duration(cls, slots: dict[str, Any]) -> int:
        try:
            start = cls._parse(slots.get("event_start"))
            end = cls._parse(slots.get("event_end"))
            return max(5, min(int((end - start).total_seconds() // 60), 1440))
        except (TypeError, ValueError):
            return int(slots.get("duration_minutes", 60) or 60)

    @staticmethod
    def _parse(value: object) -> datetime:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

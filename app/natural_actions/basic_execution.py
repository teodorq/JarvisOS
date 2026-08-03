from __future__ import annotations

from datetime import datetime
from typing import Any

from app.natural_actions.models import NaturalActionRequest


class BasicNaturalActionExecution:
    """Mail draft/send and calendar-create execution extracted from runtime."""

    INTENTS = {"mail_draft", "mail_send", "calendar_create"}

    def __init__(self, online: Any, runtime: Any) -> None:
        self.online = online
        self.runtime = runtime

    def execute(self, request: NaturalActionRequest) -> str | None:
        slots = request.slots
        if request.intent == "mail_draft":
            result = self.online.gmail.create_draft(
                slots["recipient_email"], slots["subject"], slots["body"]
            )
            slots["draft_id"] = str(result.get("draft_id", ""))
            return f"Szkic do {slots['recipient_ref']} jest gotowy. Wiadomość nie została wysłana."
        if request.intent == "mail_send":
            draft = self.online.gmail.create_draft(
                slots["recipient_email"], slots["subject"], slots["body"]
            )
            slots["draft_id"] = str(draft.get("draft_id", ""))
            self._send_verified(slots["draft_id"])
            return f"Wiadomość do {slots['recipient_ref']} została wysłana i sprawdzona w Gmail."
        if request.intent == "calendar_create":
            return self._calendar(slots)
        return None

    def _send_verified(self, draft_id: str) -> dict[str, Any]:
        live = getattr(self.online, "gmail_live", None)
        if live is not None:
            return dict(live.send_draft_verified(draft_id) or {})
        provider = getattr(self.online, "provider", None)
        sender = getattr(provider, "send_gmail_draft_verified", None)
        if callable(sender):
            return dict(sender(draft_id) or {})
        return dict(self.online.gmail.send_draft(draft_id) or {})

    def _calendar(self, slots: dict[str, Any]) -> str:
        when = datetime.fromisoformat(str(slots["when"]))
        result = self.online.calendar.create_event(
            slots["title"], when,
            duration_minutes=int(slots.get("duration_minutes", 60)),
            reminder_minutes=slots.get("reminder_minutes"),
        )
        slots.update({
            "event_id": str(result.get("event_id", "")),
            "event_title": str(result.get("title", slots["title"])),
            "end_at": str(result.get("end_at", "")),
        })
        reminder = slots.get("reminder_minutes")
        suffix = (
            f" Przypomnę {self.runtime.minutes(int(reminder))} wcześniej."
            if reminder is not None else ""
        )
        return f"Dodałem „{slots['title']}” {self.runtime.when(when)}.{suffix}"

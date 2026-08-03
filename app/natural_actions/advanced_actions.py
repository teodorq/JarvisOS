from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from app.assistant.natural_language import fold_text
from app.natural_actions.models import NaturalActionRequest


class AdvancedNaturalActions:
    """B151-B155 event lookup, mutation and existing-draft preparation."""

    INTENTS = {
        "calendar_search",
        "calendar_update",
        "calendar_delete",
        "mail_send_existing",
        "day_overview",
        "day_priority",
        "day_plan_tomorrow",
        "day_history",
        "day_mark_done",
    }

    def __init__(self, context: Any, online: Any, runtime: Any | None = None, now_provider: Any | None = None) -> None:
        self.context = context
        self.online = online
        self.runtime = runtime
        self.now_provider = now_provider or (lambda: datetime.now().astimezone())

    def prepare(self, request: NaturalActionRequest) -> None:
        if request.intent.startswith("day_"):
            self.runtime.daily.prepare(request)
            return
        if request.intent == "mail_send_existing":
            self._prepare_existing_draft(request)
            return
        self._prepare_calendar(request)

    def _prepare_existing_draft(self, request: NaturalActionRequest) -> None:
        slots = request.slots
        previous = self._latest_context_draft()
        live = getattr(self.online, "gmail_live", None)
        resolver = getattr(live, "resolve_sendable_draft", None)
        live_draft = dict(resolver() or {}) if callable(resolver) else {}
        if not live_draft and live is not None:
            live_draft = dict(live.last_draft() or {})
        if previous and self._same_draft(previous, live_draft):
            previous.update(live_draft)
        elif not previous:
            previous = live_draft
        if not previous and hasattr(self.online.gmail, "last_draft"):
            previous = dict(self.online.gmail.last_draft() or {})
        draft_id = str(previous.get("draft_id", "") or "").strip()
        if previous.get("sent"):
            request.missing = ["draft_id"]
            request.clarification = "Ostatnia odpowiedź została już wysłana. Przygotuj nowy szkic."
            return
        if not draft_id:
            request.missing = ["draft_id"]
            request.clarification = "Nie mam szkicu do wysłania. Najpierw przygotuj odpowiedź."
            return
        slots.update({
            "draft_id": draft_id,
            "recipient_ref": previous.get("recipient_ref") or previous.get("recipient") or "odbiorcy",
            "recipient_email": previous.get("recipient_email") or previous.get("recipient") or "",
            "subject": previous.get("subject") or "Wiadomość od JARVISA",
        })
        request.missing = []
        request.confirmation = (
            f"Wysłać przygotowaną odpowiedź do {slots['recipient_ref']} "
            f"z tematem „{slots['subject']}”?"
        )


    @staticmethod
    def _same_draft(first: dict[str, Any], second: dict[str, Any]) -> bool:
        left = str(first.get("draft_id", "") or "").strip()
        right = str(second.get("draft_id", "") or "").strip()
        return bool(left and right and left == right)

    def _latest_context_draft(self) -> dict[str, Any]:
        actions = [
            self.context.last_action("mail_draft"),
            self.context.last_action("gmail_reply_draft"),
        ]
        actions = [item for item in actions if item and item.get("slots")]
        actions.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return dict(actions[0].get("slots", {}) or {}) if actions else {}

    def _prepare_calendar(self, request: NaturalActionRequest) -> None:
        slots = request.slots
        if self._reuse_last_event(request):
            matches = [self._last_event(slots)]
        else:
            matches = self._find_events(slots)
        slots["matches"] = matches
        if request.intent == "calendar_search":
            request.missing = []
            request.read_only = True
            return
        if not slots.get("event_query") and not slots.get("event_id"):
            request.missing = ["event_query"]
            request.clarification = "Które wydarzenie mam zmienić? Podaj jego nazwę albo termin."
            return
        if not matches:
            request.missing = ["event_match"]
            request.clarification = "Nie znalazłem pasującego wydarzenia w kalendarzu."
            return
        if len(matches) > 1:
            request.missing = ["event_match"]
            request.clarification = self._ambiguity(matches)
            return
        event = dict(matches[0])
        slots.update({
            "event_id": event.get("id", ""),
            "event_title": event.get("title", "wydarzenie"),
            "event_start": event.get("start_at", ""),
            "event_end": event.get("end_at", ""),
        })
        if request.intent == "calendar_update" and not slots.get("new_when"):
            request.missing = ["new_when"]
            request.clarification = "Na kiedy mam przenieść to wydarzenie?"
            return
        request.missing = []
        when = self._display(event.get("start_at", ""))
        if request.intent == "calendar_delete":
            request.confirmation = f"Usunąć „{slots['event_title']}” {when}?"
        else:
            new_when = self._display(slots.get("new_when", ""))
            request.confirmation = (
                f"Przenieść „{slots['event_title']}” z {when} na {new_when}?"
            )

    def _find_events(self, slots: dict[str, Any]) -> list[dict[str, Any]]:
        start, end = self._window(slots.get("search_date"))
        query = str(slots.get("event_query", "") or "").strip()
        return list(self.online.calendar.find_events(query, start_at=start, end_at=end))

    def _reuse_last_event(self, request: NaturalActionRequest) -> bool:
        folded = fold_text(request.command)
        event_id = self.context.reference("calendar_event_id")
        if not event_id or not any(word in folded for word in ("ten", "to", "tego")):
            return False
        request.slots["event_id"] = event_id
        return True

    def _last_event(self, slots: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": slots.get("event_id", ""),
            "title": self.context.reference("calendar_event_title") or "wydarzenie",
            "start_at": self.context.reference("calendar_when"),
            "end_at": self.context.reference("calendar_end_at"),
        }

    def _window(self, search_date: object) -> tuple[datetime, datetime]:
        now = self.now_provider().astimezone()
        if search_date:
            try:
                day = datetime.fromisoformat(str(search_date)).date()
            except ValueError:
                day = now.date()
            start = datetime.combine(day, time.min, tzinfo=now.tzinfo)
            return start, start + timedelta(days=1)
        start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        return start, now + timedelta(days=30)

    @staticmethod
    def _ambiguity(matches: list[dict[str, Any]]) -> str:
        options = [
            f"{index}. {item.get('title', 'wydarzenie')} ({AdvancedNaturalActions._display(item.get('start_at', ''))})"
            for index, item in enumerate(matches[:4], start=1)
        ]
        return "Znalazłem kilka wydarzeń: " + "; ".join(options) + ". Doprecyzuj termin."

    @staticmethod
    def _display(value: object) -> str:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
        except (TypeError, ValueError):
            return "w nieznanym terminie"
        return parsed.strftime("%d.%m.%Y o %H:%M")

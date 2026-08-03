from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.online_assistant.common import OnlineAssistantError, safe_error


class CalendarWriteProviderMixin:
    """B151 confirmed Google Calendar update and delete operations."""

    def update_calendar_event(
        self,
        event_id: str,
        *,
        title: str,
        start_at: Any,
        duration_minutes: int = 60,
        reminder_minutes: int | None = None,
    ) -> dict[str, Any]:
        event_id = str(event_id).strip()
        if not event_id:
            raise OnlineAssistantError("B151: brak identyfikatora wydarzenia.")
        local_start = start_at if start_at.utcoffset() is not None else start_at.astimezone()
        local_end = local_start + timedelta(minutes=max(5, min(int(duration_minutes), 1440)))
        body: dict[str, Any] = {
            "summary": str(title)[:300],
            "start": {"dateTime": local_start.isoformat()},
            "end": {"dateTime": local_end.isoformat()},
        }
        if reminder_minutes is not None:
            minutes = max(0, min(int(reminder_minutes), 40320))
            body["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": minutes}],
            }
        try:
            service = self._service("calendar", "v3")
            service.events().patch(
                calendarId="primary",
                eventId=event_id,
                body=body,
                sendUpdates="none",
            ).execute()
            confirmed = service.events().get(
                calendarId="primary",
                eventId=event_id,
            ).execute()
            start_value = str(
                dict(confirmed.get("start", {}) or {}).get("dateTime", "")
            )
            end_value = str(
                dict(confirmed.get("end", {}) or {}).get("dateTime", "")
            )
            if not start_value or not end_value:
                raise OnlineAssistantError(
                    "B170.1: Google nie zwrócił potwierdzonego terminu wydarzenia."
                )
            return {
                "status": "GOOGLE_CALENDAR_EVENT_UPDATED",
                "event_id": str(confirmed.get("id", event_id)),
                "title": str(confirmed.get("summary", title)),
                "start_at": start_value,
                "end_at": end_value,
                "updated_at": str(confirmed.get("updated", "")),
            }
        except OnlineAssistantError:
            raise
        except Exception as error:
            raise OnlineAssistantError(
                f"B151: zmiana wydarzenia nie powiodła się: {safe_error(error)}"
            ) from None

    def delete_calendar_event(self, event_id: str) -> dict[str, Any]:
        event_id = str(event_id).strip()
        if not event_id:
            raise OnlineAssistantError("B151: brak identyfikatora wydarzenia.")
        try:
            self._service("calendar", "v3").events().delete(
                calendarId="primary", eventId=event_id, sendUpdates="none"
            ).execute()
            return {
                "status": "GOOGLE_CALENDAR_EVENT_DELETED",
                "event_id": event_id,
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"B151: usunięcie wydarzenia nie powiodło się: {safe_error(error)}"
            ) from None

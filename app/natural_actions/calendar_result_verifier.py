from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class CalendarResultVerificationError(ValueError):
    """A calendar write was not confirmed by an independent live read."""


class CalendarLiveResultVerifier:
    """Accept a calendar move only when the live event fully matches it."""

    MESSAGE = (
        "Google Calendar nie potwierdził rzeczywistej zmiany. "
        "Nie zgłaszam sukcesu. Sprawdź kalendarz i spróbuj ponownie."
    )

    def __init__(self, calendar: Any, analyzer: Any) -> None:
        self.calendar = calendar
        self.analyzer = analyzer

    def verify_move(
        self,
        write_result: dict[str, Any],
        *,
        event_id: str,
        title: str,
        start_at: datetime,
        duration_minutes: int,
    ) -> dict[str, Any]:
        result = dict(write_result or {})
        status = str(result.get("status", ""))
        returned_id = str(result.get("event_id", ""))
        if status not in {"", "GOOGLE_CALENDAR_EVENT_UPDATED"}:
            self._reject()
        if returned_id != event_id:
            self._reject()

        live = self.find_move(
            event_id=event_id,
            title=title,
            start_at=start_at,
            duration_minutes=duration_minutes,
        )
        if not live:
            self._reject()
        return live

    def find_move(
        self,
        *,
        event_id: str,
        title: str,
        start_at: datetime,
        duration_minutes: int,
    ) -> dict[str, Any]:
        expected_end = start_at + timedelta(minutes=duration_minutes)
        events = self.calendar.find_events(
            "",
            start_at=start_at - timedelta(days=1),
            end_at=expected_end + timedelta(days=1),
            max_results=100,
        )
        live = next((
            dict(item) for item in list(events or [])
            if str(item.get("id", "")) == event_id
        ), {})
        return live if self._matches(live, title, start_at, expected_end) else {}

    def _matches(
        self,
        live: dict[str, Any],
        title: str,
        expected_start: datetime,
        expected_end: datetime,
    ) -> bool:
        if not live:
            return False
        actual_start = self.analyzer.dt(live.get("start_at"))
        actual_end = self.analyzer.dt(live.get("end_at"))
        return (
            self._title(live.get("title")) == self._title(title)
            and self._same_time(actual_start, expected_start)
            and self._same_time(actual_end, expected_end)
        )

    def _reject(self) -> None:
        raise CalendarResultVerificationError(self.MESSAGE)

    @staticmethod
    def _same_time(actual: datetime | None, expected: datetime) -> bool:
        return actual is not None and abs(
            (actual - expected).total_seconds()
        ) < 60

    @staticmethod
    def _title(value: object) -> str:
        return " ".join(str(value or "").split()).casefold()

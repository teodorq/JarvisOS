from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable


class CalendarPlanStaleError(ValueError):
    """A prepared calendar move no longer matches the live calendar."""


class CalendarMovePlanGuard:
    """Reject a confirmed calendar move when its source snapshot is stale."""

    MESSAGE = (
        "Plan zmiany kalendarza jest już nieaktualny. "
        "Nie wykonałem zmiany. Poproś mnie o ponowne sprawdzenie konfliktu."
    )

    def __init__(
        self,
        calendar: Any,
        analyzer: Any,
        clear_suggestion: Callable[[], None] | None = None,
    ) -> None:
        self.calendar = calendar
        self.analyzer = analyzer
        self.clear_suggestion = clear_suggestion

    def validate(
        self,
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
    ) -> None:
        event_id = str(slots.get("event_id", "")).strip()
        original_start = self.analyzer.dt(slots.get("event_start"))
        original_end = self.analyzer.dt(slots.get("event_end"))
        if not event_id or original_start is None or original_end is None:
            self._reject()

        target_end = new_when + timedelta(minutes=duration_minutes)
        start_at = min(original_start, new_when) - timedelta(days=1)
        end_at = max(original_end, target_end) + timedelta(days=1)
        events = self.calendar.find_events(
            "", start_at=start_at, end_at=end_at, max_results=100
        )
        current = next(
            (
                dict(item)
                for item in list(events or [])
                if str(item.get("id", "")) == event_id
            ),
            {},
        )
        if not self._same_source(current, slots, original_start, original_end):
            self._reject()
        if self._target_is_busy(events, event_id, new_when, target_end):
            self._reject()

    def _same_source(
        self,
        current: dict[str, Any],
        slots: dict[str, Any],
        expected_start: datetime,
        expected_end: datetime,
    ) -> bool:
        if not current:
            return False
        current_start = self.analyzer.dt(current.get("start_at"))
        current_end = self.analyzer.dt(current.get("end_at"))
        expected_title = self._title(slots.get("event_title"))
        current_title = self._title(current.get("title"))
        return (
            bool(expected_title)
            and current_title == expected_title
            and self._same_time(current_start, expected_start)
            and self._same_time(current_end, expected_end)
        )

    def _target_is_busy(
        self,
        events: object,
        moving_id: str,
        target_start: datetime,
        target_end: datetime,
    ) -> bool:
        for raw in list(events or []):
            event = dict(raw or {})
            if str(event.get("id", "")) == moving_id:
                continue
            start = self.analyzer.dt(event.get("start_at"))
            end = self.analyzer.dt(event.get("end_at"))
            if start is not None and end is not None:
                if target_start < end and target_end > start:
                    return True
        return False

    def _reject(self) -> None:
        if self.clear_suggestion is not None:
            self.clear_suggestion()
        raise CalendarPlanStaleError(self.MESSAGE)

    @staticmethod
    def _same_time(actual: datetime | None, expected: datetime) -> bool:
        return actual is not None and abs(
            (actual - expected).total_seconds()
        ) < 60

    @staticmethod
    def _title(value: object) -> str:
        return " ".join(str(value or "").split()).casefold()

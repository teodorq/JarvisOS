"""Display the declared Azure PAPER schedule; never starts or controls a job."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any


# Only the supported weekday UTC window is interpreted. Unknown or changed
# formats must keep the ordinary stale-data warning, not imply a safe pause.
_WEEKDAY_WINDOW = re.compile(r"([0-9]{1,2}(?:,[0-9]{1,2}){0,11}) ([0-9]{1,2})-([0-9]{1,2}) \* \* 1-5")
_LAST_CYCLE_GRACE = timedelta(minutes=10)


def _parse(value: object) -> tuple[tuple[int, ...], int, int] | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    match = _WEEKDAY_WINDOW.fullmatch(value)
    if match is None:
        return None
    minutes = tuple(map(int, match.group(1).split(",")))
    start, end = int(match.group(2)), int(match.group(3))
    if minutes != tuple(sorted(set(minutes))) or minutes[-1] > 59 or not 0 <= start <= end < 24:
        return None
    return minutes, start, end


def declared_paper_cron(value: object) -> str:
    return value if isinstance(value, str) and _parse(value) is not None else ""


def paper_schedule_projection(
    declared: object,
    *,
    now: datetime,
    observed: datetime,
    completed_and_verified: bool,
) -> dict[str, Any]:
    window = _parse(declared)
    if window is None:
        return {}
    minutes, first_hour, last_hour = window
    selected = now.astimezone(timezone.utc)
    midnight = selected.replace(hour=0, minute=0, second=0, microsecond=0)
    next_slot = None
    previous_window_end = None
    inside_window = False
    for day_offset in range(-7, 8):
        day = midnight + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        first = day.replace(hour=first_hour, minute=minutes[0])
        last = day.replace(hour=last_hour, minute=minutes[-1])
        if first <= selected <= last:
            inside_window = True
        if last <= selected:
            previous_window_end = last
        if next_slot is None and last > selected:
            next_slot = next(
                slot for hour in range(first_hour, last_hour + 1) for minute in minutes
                if (slot := day.replace(hour=hour, minute=minute)) > selected
            )

    expected_pause = bool(
        completed_and_verified and not inside_window and previous_window_end is not None
        and previous_window_end <= observed <= min(selected, previous_window_end + _LAST_CYCLE_GRACE)
    )
    return {
        "schedule_pause_expected": expected_pause,
        "next_scheduled_cycle_at": next_slot.isoformat() if next_slot is not None else "",
    }

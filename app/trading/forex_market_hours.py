"""Single lightweight Forex market-hours policy shared by all views."""

from __future__ import annotations

from datetime import datetime, timezone


def forex_market_open(now: datetime) -> bool:
    """Return whether the project's conservative Forex window is open."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    selected = now.astimezone(timezone.utc)
    weekday = selected.weekday()
    if weekday <= 3:
        return True
    if weekday == 4:
        return selected.hour < 21
    if weekday == 5:
        return False
    return selected.hour >= 22


__all__ = ["forex_market_open"]

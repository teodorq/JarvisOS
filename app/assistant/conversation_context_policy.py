from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


FOLLOWUP_TTL = timedelta(hours=1)
MAX_CLOCK_SKEW = timedelta(minutes=5)


def context_for_resolution(
    value: object, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Hide stale follow-up pointers without deleting the conversation history."""
    data = dict(value or {}) if isinstance(value, dict) else {}
    if _is_fresh(data.get("updated_at"), now=now):
        return data
    for key in ("last_command", "last_intent", "last_target"):
        data[key] = ""
    return data


def _is_fresh(value: object, *, now: datetime | None = None) -> bool:
    try:
        updated = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age = current.astimezone(timezone.utc) - updated.astimezone(timezone.utc)
    return -MAX_CLOCK_SKEW <= age <= FOLLOWUP_TTL


__all__ = ["FOLLOWUP_TTL", "context_for_resolution"]

from __future__ import annotations

import time
from typing import Any

from app.natural_actions.validation import classify_confirmation


_TTL_SECONDS = 180.0
_STATE_ATTR = "_last_confirmed_calendar_write"


def remember_confirmed_calendar_write(window: Any, thought: dict[str, Any]) -> None:
    """Keep one bounded confirmed calendar plan for harmless duplicate checks."""
    if not _eligible(thought):
        return
    now = time.monotonic()
    fingerprint = str(thought.get("operation_fingerprint", "")).strip()
    current = getattr(window, _STATE_ATTR, None)
    if isinstance(current, dict):
        same = str(current.get("fingerprint", "")) == fingerprint
        if same and float(current.get("expires_at", 0.0) or 0.0) > now:
            return
    setattr(window, _STATE_ATTR, {
        "thought": dict(thought),
        "fingerprint": fingerprint,
        "expires_at": now + _TTL_SECONDS,
    })


def repeated_calendar_confirmation(
    window: Any, answer: object
) -> dict[str, Any] | None:
    """Return the recent exact plan only for a repeated positive confirmation."""
    if classify_confirmation(answer).kind != "accept":
        return None
    current = getattr(window, _STATE_ATTR, None)
    if not isinstance(current, dict):
        return None
    if float(current.get("expires_at", 0.0) or 0.0) <= time.monotonic():
        setattr(window, _STATE_ATTR, None)
        return None
    thought = dict(current.get("thought", {}) or {})
    return thought if _eligible(thought) else None


def _eligible(thought: dict[str, Any]) -> bool:
    return (
        bool(thought.get("natural_action"))
        and str(thought.get("assistant_intent", ""))
        in {"active_apply_suggestion", "active_undo_calendar"}
        and not bool(thought.get("read_only", False))
        and bool(str(thought.get("operation_fingerprint", "")).strip())
    )

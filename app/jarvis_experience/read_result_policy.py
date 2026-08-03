from __future__ import annotations

from typing import Any

from app.jarvis_experience.isolation import ClientIsolationPolicy


TRUSTED_READ_INTENTS = frozenset({
    "active_apply_suggestion",
    "active_conflict_move",
    "active_undo_calendar",
    "gmail_search",
    "gmail_read",
    "gmail_thread",
    "gmail_reply_draft",
    "mail_send_existing",
    "gmail_latest",
    "gmail_priority",
    "calendar_today",
    "calendar_conflicts",
    "calendar_status",
    "drive_search",
    "drive_summarize",
    "document_search",
    "document_status",
    "reminder_status",
    "day_overview",
    "report_review",
})


def sanitize_task_result(result: object, thought: dict[str, Any]) -> str:
    """Keep layout only for allowlisted, trusted client-facing results."""
    intent = str(thought.get("assistant_intent", ""))
    trusted_source = bool(thought.get("natural_action")) or bool(
        thought.get("read_only")
    )
    if trusted_source and intent in TRUSTED_READ_INTENTS:
        return ClientIsolationPolicy.sanitize_action_result(result)
    return ClientIsolationPolicy.sanitize_text(result)

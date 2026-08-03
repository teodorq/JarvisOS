from __future__ import annotations

from typing import Any

from app.natural_actions.planned_execution import PlannedNaturalActionExecutor


_EXACT_CALENDAR_INTENTS = {
    "active_apply_suggestion",
    "active_conflict_move",
    "active_undo_calendar",
}
_EXACT_SHARED_INTENTS = _EXACT_CALENDAR_INTENTS | {"mail_send_existing"}


def is_exact_calendar_plan(thought: dict[str, Any]) -> bool:
    """Return True only for a complete prepared calendar-write plan."""
    return (
        bool(thought.get("natural_action"))
        and str(thought.get("handler", "")) == "personal_assistant"
        and str(thought.get("assistant_intent", ""))
        in _EXACT_CALENDAR_INTENTS
        and bool(str(thought.get("operation_fingerprint", "")).strip())
    )


def execute_confirmed_calendar_plan(
    window: Any,
    thought: dict[str, Any],
) -> Any:
    """Execute exact confirmed calendar and Gmail plans on the shared assistant."""
    exact_shared = (
        bool(thought.get("natural_action"))
        and str(thought.get("handler", "")) == "personal_assistant"
        and str(thought.get("assistant_intent", "")) in _EXACT_SHARED_INTENTS
        and bool(str(thought.get("operation_fingerprint", "")).strip())
    )
    if not exact_shared:
        return window.brain.execute(thought)

    assistant = getattr(window, "assistant", None)
    if assistant is None:
        assistant = getattr(
            getattr(window, "brain", None),
            "personal_assistant_controller",
            None,
        )
    natural = getattr(assistant, "natural_actions", None)
    runtime = getattr(natural, "runtime", None)
    if not callable(getattr(runtime, "execute_once", None)):
        return window.brain.execute(thought)
    return PlannedNaturalActionExecutor.execute(assistant, dict(thought))

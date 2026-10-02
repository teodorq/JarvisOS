"""Strict one-pass path for inexpensive, owner-authorized local reads."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


_FAST_LOCAL_INTENTS = frozenset({
    "current_time",
    "device_status",
    "capability_help",
    "assistant_status",
    "conversation_status",
    "memory_status",
    "voice_status",
    "desktop_status",
    "daily_status",
    "integration_status",
    "paper_trading_status",
    "forex_observation_review",
})


def is_fast_local_read(thought: object) -> bool:
    """Accept only explicit, context-free and action-free local reads."""
    if not isinstance(thought, Mapping):
        return False
    actions = thought.get("actions")
    return bool(
        thought.get("handler") == "personal_assistant"
        and thought.get("assistant_intent") in _FAST_LOCAL_INTENTS
        and thought.get("read_only") is True
        and thought.get("can_execute") is True
        and isinstance(actions, list)
        and not actions
        and thought.get("used_context") is False
        and not thought.get("clarification")
        and thought.get("requires_confirmation") is not True
        and thought.get("natural_action") is not True
    )


class FastLocalCommandService:
    """Execute a verified local read once, without the general planner."""

    @staticmethod
    def try_execute(
        assistant: Any,
        command: str,
        *,
        authorize: Callable[..., Mapping[str, Any]],
    ) -> dict[str, Any] | None:
        matches = getattr(assistant, "matches", None)
        plan = getattr(assistant, "plan", None)
        handle = getattr(assistant, "handle", None)
        if not (
            callable(matches)
            and callable(plan)
            and callable(handle)
            and matches(command)
        ):
            return None

        thought = plan(command)
        if not is_fast_local_read(thought):
            return None

        try:
            authorization = authorize(command, read_only=True)
        except Exception:
            return {
                "handler": "fast_local_denied",
                "message": "Nie udało się bezpiecznie sprawdzić uprawnień.",
            }
        if not isinstance(authorization, Mapping) or not authorization.get(
            "allowed", False
        ):
            reason = (
                str(authorization.get("reason", "brak uprawnienia"))
                if isinstance(authorization, Mapping)
                else "brak uprawnienia"
            )
            return {
                "handler": "fast_local_denied",
                "message": f"Nie mam uprawnień: {reason}",
            }

        response = str(handle(command)).strip()
        if not response:
            response = "Nie udało się przygotować lokalnej odpowiedzi."
        return {
            "handler": "fast_local_response",
            "assistant_intent": str(thought.get("assistant_intent", "")),
            "message": response,
            "read_only": True,
        }


__all__ = ["FastLocalCommandService", "is_fast_local_read"]

from __future__ import annotations

import hmac
from typing import Any

from app.natural_actions.models import NaturalActionRequest


class PlannedNaturalActionExecutor:
    """Execute the exact natural-action plan that the user confirmed."""

    @staticmethod
    def execute(assistant: Any, thought: dict[str, Any]) -> str:
        natural = getattr(assistant, "natural_actions", None)
        if natural is None:
            raise ValueError("Natural actions are unavailable.")

        if not bool(thought.get("natural_action")):
            return str(assistant.handle(str(thought.get("command", ""))))

        intent = str(thought.get("assistant_intent", "")).strip()
        slots = dict(thought.get("natural_slots", {}) or {})
        command = str(thought.get("command", "")).strip()
        expected = str(thought.get("operation_fingerprint", "")).strip()

        request = NaturalActionRequest(
            original=str(thought.get("original_command", command)),
            command=command,
            intent=intent,
            confidence=1.0,
            slots=slots,
            missing=[],
            clarification="",
            confirmation=str(thought.get("confirmation_message", "")),
            used_context=bool(thought.get("used_context", False)),
            read_only=bool(thought.get("read_only", False)),
        )

        if not request.can_execute or intent in {"standard", "cancel"}:
            raise ValueError("Confirmed natural-action plan is not executable.")
        if not expected:
            raise ValueError("Confirmed natural-action plan has no fingerprint.")

        actual = natural.runtime.fingerprint(request)
        if not hmac.compare_digest(expected, actual):
            raise ValueError("Confirmed natural-action plan changed before execution.")

        natural.context.clear_pending()
        response = natural.runtime.execute_once(request)
        natural.context.remember(request, response)
        return str(response)

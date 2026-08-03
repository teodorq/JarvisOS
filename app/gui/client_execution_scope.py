from __future__ import annotations

from typing import Any

from app.gui.client_capability_policy import ClientCapabilityPolicy


_SCOPE_ATTR = "_jarvis_client_scope_token"
_SCOPE_KEY = "_jarvis_client_scope"


def scope_client_thought(window: Any, thought: object) -> dict[str, Any]:
    """Mark a plan with an in-memory token that model output cannot forge."""
    planned = dict(thought or {}) if isinstance(thought, dict) else {}
    if not bool(getattr(window, "_client_scope_enforced", False)):
        return planned
    token = getattr(window, _SCOPE_ATTR, None)
    if token is None:
        token = object()
        setattr(window, _SCOPE_ATTR, token)
    planned[_SCOPE_KEY] = token
    return planned


def executable_client_thought(thought: object) -> dict[str, Any]:
    """Remove the private UI token before handing a plan to the brain."""
    planned = dict(thought or {}) if isinstance(thought, dict) else {}
    planned.pop(_SCOPE_KEY, None)
    return planned


def client_execution_denial(window: Any, thought: object) -> str:
    """Deny owner plans and plans not created by this client session."""
    denial = ClientCapabilityPolicy.denial_for_thought(thought)
    if denial:
        return denial
    if not bool(getattr(window, "_client_scope_enforced", False)):
        return ""
    token = getattr(window, _SCOPE_ATTR, None)
    if (
        token is None or not isinstance(thought, dict)
        or thought.get(_SCOPE_KEY) is not token
    ):
        return (
            "Tego działania nie przygotowano w trybie klienta. "
            "Aby je zatwierdzić, wróć do panelu właściciela."
        )
    return ""


def approve_client_thought(window: Any, thought: object) -> bool:
    """Publish a natural denial and stop before any owner-side execution."""
    denial = client_execution_denial(window, thought)
    if not denial:
        return True
    window._publish_client_event(state="error", message=denial, progress=100)
    window.say_safe(denial)
    return False

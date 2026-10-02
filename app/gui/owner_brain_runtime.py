from __future__ import annotations

from typing import Any

from app.ai.client_brain import ensure_owner_brain


def activate_owner_brain(window: Any) -> Any:
    """Upgrade the lightweight core immediately before an owner command."""
    owner = ensure_owner_brain(
        getattr(window, "brain", None),
        getattr(window, "assistant", None),
        getattr(window, "project_root", None),
    )
    window.brain = owner
    return owner

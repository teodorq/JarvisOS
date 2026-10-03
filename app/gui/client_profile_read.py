from __future__ import annotations

from typing import Any


def read_client_profile(controller: Any) -> dict[str, Any]:
    """Prefer the lightweight profile API while retaining legacy adapters."""
    profile_reader = getattr(controller, "profile", None)
    if callable(profile_reader):
        return dict(profile_reader() or {})
    status_reader = getattr(controller, "status", None)
    status = dict(status_reader() or {}) if callable(status_reader) else {}
    return dict(status.get("profile", {}) or {})


__all__ = ["read_client_profile"]

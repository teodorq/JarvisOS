from __future__ import annotations

from typing import Any


def should_start_client(controller: Any, config: object) -> bool:
    """Resolve a safe startup screen while preserving first-run setup."""
    payload = config if isinstance(config, dict) else {}
    ui = dict(payload.get("ui", {}) or {})
    mode = str(ui.get("startup_mode", "remember")).strip().casefold()
    if mode == "owner":
        return False
    if mode == "client":
        try:
            return bool(controller.profile().get("setup_completed", False))
        except Exception:
            return False
    try:
        return bool(controller.should_start_client())
    except Exception:
        return False


__all__ = ["should_start_client"]

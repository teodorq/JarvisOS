from __future__ import annotations

from typing import Any


def business_service_snapshot(window: Any) -> tuple[str, bool]:
    """Refresh slower service checks periodically while metrics stay live."""
    tick = int(getattr(window, "_status_tick", 0) or 0)
    cached = getattr(window, "_business_service_status_cache", None)
    if cached is not None and tick % 5:
        return cached
    try:
        background = window._background_status()
    except Exception:
        background = "OFFLINE"
    try:
        online = bool(
            window.assistant.online.status()["connection"]["token_present"]
        )
    except Exception:
        online = False
    result = (background, online)
    window._business_service_status_cache = result
    return result

"""Pause client-only observers when the owner dashboard takes focus."""

from __future__ import annotations

from typing import Any


_RUNTIME_ATTRIBUTES = (
    "_forex_activity_runtime_service",
    "_live_conflict_refresh_service",
    "_startup_conflict_runtime_service",
)


def suspend_client_observers(window: Any) -> None:
    """Stop periodic client reads without touching shared remote runtimes."""
    timer = getattr(window, "_proactive_timer", None)
    if timer is not None:
        timer.stop()
    for attribute in _RUNTIME_ATTRIBUTES:
        runtime = getattr(window, attribute, None)
        runtime_timer = getattr(runtime, "timer", None)
        if runtime_timer is not None:
            runtime_timer.stop()


def resume_client_observers(window: Any) -> None:
    """Resume already-created observers when the client view is restored."""
    timer = getattr(window, "_proactive_timer", None)
    if timer is not None and not timer.isActive():
        timer.start()
    for attribute in _RUNTIME_ATTRIBUTES:
        runtime = getattr(window, attribute, None)
        arm = getattr(runtime, "arm", None)
        if callable(arm):
            arm()


__all__ = ["resume_client_observers", "suspend_client_observers"]

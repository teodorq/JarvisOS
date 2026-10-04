from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.performance_profile import (
    PerformanceProfile,
    load_performance_profile,
)


def apply_runtime_preferences(
    owner_window: Any,
    project_root: str | Path | None = None,
) -> PerformanceProfile | None:
    root = project_root or getattr(owner_window, "project_root", None)
    if root is None:
        return None
    profile = load_performance_profile(root)
    owner_window.performance_profile = profile
    _set_interval(owner_window, "timer", profile.owner_metrics_interval_ms)
    _set_interval(
        owner_window, "_forex_activity_timer", profile.owner_forex_interval_ms
    )
    client = getattr(owner_window, "client_window", None)
    if client is None:
        return profile
    halo = getattr(client, "halo", None)
    apply_halo = getattr(halo, "set_performance_profile", None)
    if callable(apply_halo):
        apply_halo(profile)
    forex = getattr(client, "_forex_activity_runtime_service", None)
    _set_runtime_timer(forex, profile.client_forex_interval_ms)
    calendar = getattr(client, "_live_conflict_refresh_service", None)
    _set_runtime_timer(calendar, profile.calendar_refresh_interval_ms)
    presenter = getattr(client, "presenter", None)
    sound = getattr(presenter, "sound_theme", None)
    apply_sound = getattr(sound, "apply_preferences", None)
    if callable(apply_sound):
        config = getattr(owner_window, "business_config", {})
        enabled = bool(dict(config.get("sound", {}) or {}).get(
            "effects_enabled", True
        ))
        apply_sound(enabled=enabled, performance_profile=profile)
    return profile


def _set_interval(window: Any, name: str, interval: int) -> None:
    attributes = getattr(window, "__dict__", {})
    timer = attributes.get(name) if isinstance(attributes, dict) else None
    setter = getattr(timer, "setInterval", None)
    if callable(setter):
        setter(int(interval))


def _set_runtime_timer(runtime: Any, interval: int) -> None:
    timer = getattr(runtime, "timer", None)
    setter = getattr(timer, "setInterval", None)
    if callable(setter):
        setter(int(interval))


__all__ = ["apply_runtime_preferences"]

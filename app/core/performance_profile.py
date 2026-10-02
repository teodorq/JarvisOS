from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Callable

import psutil

from app.core.project_paths import resolve_project_root


@dataclass(frozen=True)
class PerformanceProfile:
    name: str
    lazy_voice: bool
    orb_stride_multiplier: int
    active_frame_interval_ms: int
    idle_frame_interval_ms: int
    sound_theme_enabled: bool


BALANCED = PerformanceProfile(
    name="balanced",
    lazy_voice=True,
    orb_stride_multiplier=1,
    active_frame_interval_ms=33,
    idle_frame_interval_ms=50,
    sound_theme_enabled=True,
)
LOW_RESOURCE = PerformanceProfile(
    name="low_resource",
    lazy_voice=True,
    orb_stride_multiplier=2,
    active_frame_interval_ms=50,
    idle_frame_interval_ms=80,
    sound_theme_enabled=False,
)


def _system_capacity() -> tuple[int, int]:
    return int(psutil.virtual_memory().total), int(psutil.cpu_count() or 1)


def load_performance_profile(
    project_root: str | Path | None = None,
    *,
    environment: dict[str, str] | None = None,
    system_probe: Callable[[], tuple[int, int]] | None = None,
) -> PerformanceProfile:
    """Select a bounded UI profile without making startup depend on config I/O."""
    root = Path(project_root or resolve_project_root()).resolve()
    selected = "auto"
    try:
        payload = json.loads(
            (root / "config" / "performance.json").read_text(encoding="utf-8")
        )
        selected = str(payload.get("profile", "auto")).strip().casefold()
    except (OSError, ValueError, TypeError):
        pass

    source = os.environ if environment is None else environment
    selected = str(
        source.get("JARVIS_OS_PERFORMANCE_PROFILE", selected)
    ).strip().casefold()
    if selected == "low_resource":
        return LOW_RESOURCE
    if selected == "balanced":
        return BALANCED

    try:
        total_memory, logical_cpus = (system_probe or _system_capacity)()
    except Exception:
        return BALANCED
    if total_memory <= 8 * 1024**3 or logical_cpus <= 4:
        return LOW_RESOURCE
    return BALANCED

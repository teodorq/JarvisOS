from __future__ import annotations

from typing import Any

from app.core.performance_profile import PerformanceProfile
from app.gui.orb_frame_budget import OrbFrameBudget


def apply_halo_performance(
    halo: Any,
    profile: PerformanceProfile,
) -> None:
    halo.performance_profile = profile
    halo._frame_budget = OrbFrameBudget(
        initial_stride_multiplier=profile.orb_stride_multiplier
    )
    halo._baseline_stride_multiplier = halo._frame_budget.stride_multiplier
    if halo._timer.isActive():
        halo._timer.setInterval(halo._frame_interval_ms())
    halo.update()


__all__ = ["apply_halo_performance"]

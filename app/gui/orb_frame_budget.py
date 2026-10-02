from __future__ import annotations


class OrbFrameBudget:
    """Adapt orb detail with hysteresis while preserving continuous motion."""

    MAX_STRIDE_MULTIPLIER = 3

    def __init__(
        self,
        *,
        active_render_budget_ms: float = 25.0,
        idle_render_budget_ms: float = 40.0,
        degrade_after: int = 3,
        recover_after: int = 90,
    ) -> None:
        self._active_render_budget_ms = max(1.0, active_render_budget_ms)
        self._idle_render_budget_ms = max(1.0, idle_render_budget_ms)
        self._degrade_after = max(1, degrade_after)
        self._recover_after = max(1, recover_after)
        self._stride_multiplier = 1
        self._slow_frames = 0
        self._fast_frames = 0

    @property
    def stride_multiplier(self) -> int:
        return self._stride_multiplier

    def observe(self, render_ms: float, *, active: bool) -> int:
        """Record one render and return the detail multiplier for next frame."""
        budget = (
            self._active_render_budget_ms
            if active
            else self._idle_render_budget_ms
        )
        duration = max(0.0, float(render_ms))
        if duration > budget:
            self._slow_frames += 1
            self._fast_frames = 0
            if self._slow_frames >= self._degrade_after:
                self._stride_multiplier = min(
                    self.MAX_STRIDE_MULTIPLIER,
                    self._stride_multiplier + 1,
                )
                self._slow_frames = 0
            return self._stride_multiplier

        if duration < budget * 0.45:
            self._fast_frames += 1
            self._slow_frames = 0
            if self._fast_frames >= self._recover_after:
                self._stride_multiplier = max(1, self._stride_multiplier - 1)
                self._fast_frames = 0
            return self._stride_multiplier

        self._slow_frames = 0
        self._fast_frames = 0
        return self._stride_multiplier

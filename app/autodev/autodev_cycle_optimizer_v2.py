from __future__ import annotations

from typing import Any


class AutoDevCycleOptimizerV2:
    def optimize(
        self,
        *,
        ranking: dict[str, Any],
        history: dict[str, Any],
    ) -> dict[str, Any]:
        selected = ranking.get("selected")

        if not isinstance(selected, dict):
            return {
                "success": True,
                "status": "NO_SELECTION",
                "selected": None,
            }

        success_rate = float(
            history.get(
                "success_rate",
                0.0,
            )
            or 0.0
        )

        optimized = dict(selected)

        if success_rate < 0.5:
            optimized[
                "risk_score"
            ] = min(
                float(
                    optimized.get(
                        "risk_score",
                        0.0,
                    )
                )
                + 10.0,
                100.0,
            )

        return {
            "success": True,
            "status": "CYCLE_OPTIMIZED",
            "selected": optimized,
            "safe_mode": True,
            "requires_approval": True,
        }

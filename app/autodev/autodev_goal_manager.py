from __future__ import annotations

from typing import Any


class AutoDevGoalManager:
    def normalize(
        self,
        goal: str,
    ) -> dict[str, Any]:
        normalized = " ".join(
            str(goal).strip().split()
        )

        if not normalized:
            return {
                "success": False,
                "status": "EMPTY_GOAL",
                "goal": "",
            }

        return {
            "success": True,
            "status": "GOAL_READY",
            "goal": normalized,
            "safe_mode": True,
            "requires_approval": True,
        }

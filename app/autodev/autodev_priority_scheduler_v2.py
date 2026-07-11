from __future__ import annotations

from typing import Any


class AutoDevPrioritySchedulerV2:
    def build_schedule(
        self,
        ranked: list[dict[str, Any]],
        *,
        limit: int = 5,
    ) -> dict[str, Any]:
        safe_limit = max(1, int(limit))

        scheduled = [
            dict(item)
            for item in ranked[:safe_limit]
            if isinstance(item, dict)
        ]

        return {
            "success": True,
            "status": (
                "SCHEDULE_READY"
                if scheduled
                else "NO_TASKS"
            ),
            "count": len(scheduled),
            "schedule": scheduled,
        }

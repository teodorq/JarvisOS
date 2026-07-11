from __future__ import annotations

from typing import Any


class AutoDevGoalSelector:
    def select(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:

        valid = [
            dict(item)
            for item in candidates
            if isinstance(item, dict)
            and str(
                item.get(
                    "goal",
                    item.get(
                        "title",
                        "",
                    ),
                )
            ).strip()
        ]

        if not valid:
            return {
                "success": True,
                "status": "NO_GOALS",
                "selected": None,
            }

        valid.sort(
            key=lambda item: float(
                item.get(
                    "priority_score",
                    0.0,
                )
                or 0.0
            ),
            reverse=True,
        )

        selected = valid[0]

        return {
            "success": True,
            "status": "GOAL_SELECTED",
            "selected": selected,
            "count": len(valid),
        }

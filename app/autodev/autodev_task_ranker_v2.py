from __future__ import annotations

from typing import Any


class AutoDevTaskRankerV2:
    def rank(
        self,
        goals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ranked: list[dict[str, Any]] = []

        for item in goals:
            if not isinstance(item, dict):
                continue

            goal = str(
                item.get(
                    "goal",
                    "",
                )
            ).strip()

            if not goal:
                continue

            priority = self._float(
                item.get(
                    "priority_score",
                    0.0,
                )
            )
            value = self._float(
                item.get(
                    "value_score",
                    0.0,
                )
            )
            risk = self._float(
                item.get(
                    "risk_score",
                    0.0,
                )
            )

            final_score = round(
                priority
                + value
                - risk,
                2,
            )

            ranked.append(
                {
                    **dict(item),
                    "final_score": final_score,
                }
            )

        ranked.sort(
            key=lambda item: item["final_score"],
            reverse=True,
        )

        return {
            "success": True,
            "status": (
                "TASKS_RANKED"
                if ranked
                else "NO_TASKS"
            ),
            "ranked": ranked,
            "selected": (
                ranked[0]
                if ranked
                else None
            ),
        }

    def _float(
        self,
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

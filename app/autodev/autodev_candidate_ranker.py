from __future__ import annotations

from typing import Any


class AutoDevCandidateRanker:
    def rank(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:

        ranked: list[dict[str, Any]] = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            goal = str(
                candidate.get(
                    "goal",
                    candidate.get(
                        "title",
                        "",
                    ),
                )
            ).strip()

            if not goal:
                continue

            priority = self._float(
                candidate.get(
                    "priority_score",
                    0.0,
                )
            )

            value = self._float(
                candidate.get(
                    "value_score",
                    0.0,
                )
            )

            risk = self._float(
                candidate.get(
                    "risk_score",
                    candidate.get(
                        "predicted_risk",
                        0.0,
                    ),
                )
            )

            effort = self._float(
                candidate.get(
                    "effort_score",
                    candidate.get(
                        "estimated_effort",
                        0.0,
                    ),
                )
            )

            final_score = round(
                priority
                + value
                - risk
                - effort,
                2,
            )

            ranked.append(
                {
                    **dict(candidate),
                    "goal": goal,
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
                "CANDIDATES_RANKED"
                if ranked
                else "NO_CANDIDATES"
            ),
            "count": len(ranked),
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

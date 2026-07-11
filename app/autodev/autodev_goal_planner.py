from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AutoDevPlannedGoal:
    goal_id: str
    goal: str
    priority_score: float
    risk_score: float
    value_score: float
    source: str = "AutoDevGoalPlanner"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutoDevGoalPlanner:
    """
    Buduje uporządkowaną listę celów dla AutoDev.

    Moduł nie wykonuje zmian i nie zapisuje kodu.
    """

    def __init__(
        self,
        max_goals: int = 20,
    ) -> None:
        self.max_goals = max(1, int(max_goals))
        self.last_result: dict[str, Any] | None = None

    def plan(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:

        planned: list[AutoDevPlannedGoal] = []

        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue

            goal = str(
                candidate.get(
                    "goal",
                    candidate.get(
                        "title",
                        candidate.get(
                            "description",
                            "",
                        ),
                    ),
                )
            ).strip()

            if not goal:
                continue

            priority_score = self._float(
                candidate.get(
                    "priority_score",
                    0.0,
                )
            )

            risk_score = self._float(
                candidate.get(
                    "risk_score",
                    candidate.get(
                        "predicted_risk",
                        0.0,
                    ),
                )
            )

            value_score = self._float(
                candidate.get(
                    "value_score",
                    0.0,
                )
            )

            goal_id = str(
                candidate.get(
                    "goal_id",
                    candidate.get(
                        "task_id",
                        f"goal-{index + 1}",
                    ),
                )
            )

            planned.append(
                AutoDevPlannedGoal(
                    goal_id=goal_id,
                    goal=goal,
                    priority_score=priority_score,
                    risk_score=risk_score,
                    value_score=value_score,
                    metadata=dict(
                        candidate.get(
                            "metadata"
                        )
                        or {}
                    ),
                )
            )

        planned.sort(
            key=lambda item: (
                item.priority_score
                + item.value_score
                - item.risk_score
            ),
            reverse=True,
        )

        planned = planned[
            :self.max_goals
        ]

        result = {
            "success": True,
            "status": (
                "GOALS_PLANNED"
                if planned
                else "NO_GOALS"
            ),
            "count": len(planned),
            "goals": [
                item.to_dict()
                for item in planned
            ],
            "selected": (
                planned[0].to_dict()
                if planned
                else None
            ),
        }

        self.last_result = dict(result)
        return result

    def _float(
        self,
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def status(self) -> dict[str, Any]:
        return {
            "max_goals": self.max_goals,
            "last_result": self.last_result,
        }

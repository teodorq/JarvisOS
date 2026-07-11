from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AutoDevGoalRecord:
    goal_id: str
    goal: str
    priority_score: float = 0.0
    risk_score: float = 0.0
    value_score: float = 0.0
    status: str = "PENDING"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutoDevGoalRepositoryV2:
    def __init__(self) -> None:
        self._goals: dict[str, AutoDevGoalRecord] = {}

    def add(
        self,
        goal: AutoDevGoalRecord,
    ) -> dict[str, Any]:
        self._goals[goal.goal_id] = goal
        return goal.to_dict()

    def get(
        self,
        goal_id: str,
    ) -> dict[str, Any] | None:
        item = self._goals.get(str(goal_id))

        return (
            item.to_dict()
            if item is not None
            else None
        )

    def list_all(self) -> list[dict[str, Any]]:
        return [
            item.to_dict()
            for item in self._goals.values()
        ]

    def update_status(
        self,
        goal_id: str,
        status: str,
    ) -> dict[str, Any] | None:
        item = self._goals.get(str(goal_id))

        if item is None:
            return None

        item.status = str(status).upper()
        return item.to_dict()

    def status(self) -> dict[str, Any]:
        return {
            "count": len(self._goals),
            "goals": self.list_all(),
        }

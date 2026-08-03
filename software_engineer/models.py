from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ImplementationTask:
    task_id: str
    title: str
    description: str
    category: str
    priority: str
    estimated_minutes: int
    estimated_roi: float
    estimated_risk: float
    dependencies: list[str] = field(default_factory=list)
    parallel_group: int = 0
    acceptance_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImplementationPlan:
    objective: str
    tasks: list[ImplementationTask]
    execution_order: list[str]
    parallel_groups: list[list[str]]
    total_estimated_minutes: int
    average_roi: float
    average_risk: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "tasks": [
                task.to_dict()
                for task in self.tasks
            ],
            "execution_order": list(
                self.execution_order
            ),
            "parallel_groups": [
                list(group)
                for group in self.parallel_groups
            ],
            "total_estimated_minutes": (
                self.total_estimated_minutes
            ),
            "average_roi": self.average_roi,
            "average_risk": self.average_risk,
        }

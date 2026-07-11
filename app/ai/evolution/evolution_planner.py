from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class EvolutionPlan:
    plan_id: str
    objective: str
    mode: str
    priority: str
    iterations: int
    requires_approval: bool
    steps: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvolutionPlanner:

    def build(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        iterations: int = 5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        context = dict(context or {})

        steps = [
            {
                "order": 1,
                "name": "Analiza projektu",
                "type": "ANALYZE",
            },
            {
                "order": 2,
                "name": "Wykrycie ulepszeń",
                "type": "DETECT",
            },
            {
                "order": 3,
                "name": "Uruchomienie Continuous Developer",
                "type": "EXECUTE",
            },
            {
                "order": 4,
                "name": "Walidacja i nauka",
                "type": "LEARN",
            },
        ]

        plan = EvolutionPlan(
            plan_id=f"evolution_plan_{uuid4().hex}",
            objective=str(objective),
            mode=str(mode).upper(),
            priority=context.get("priority", "HIGH"),
            iterations=max(1, int(iterations)),
            requires_approval=str(mode).upper() != "AUTONOMOUS",
            steps=steps,
            metadata=context,
        )

        return plan.to_dict()

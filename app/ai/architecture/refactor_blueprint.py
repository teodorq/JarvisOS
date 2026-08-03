from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .module_split_planner import ModuleSplitPlan


@dataclass
class RefactorBlueprint:
    title: str
    objective: str
    targets: list[str]
    steps: list[str]
    safeguards: list[str]
    expected_outcomes: list[str]
    priority: str
    estimated_risk: float
    estimated_roi: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "objective": self.objective,
            "targets": list(self.targets),
            "steps": list(self.steps),
            "safeguards": list(self.safeguards),
            "expected_outcomes": list(self.expected_outcomes),
            "priority": self.priority,
            "estimated_risk": self.estimated_risk,
            "estimated_roi": self.estimated_roi,
            "metadata": dict(self.metadata),
        }


class RefactorBlueprintBuilder:

    def from_split_plan(
        self,
        plan: ModuleSplitPlan,
    ) -> RefactorBlueprint:
        return RefactorBlueprint(
            title=f"Refactor: {plan.target}",
            objective=plan.reason,
            targets=[
                plan.target,
                *plan.proposed_modules,
            ],
            steps=list(plan.migration_steps),
            safeguards=[
                "Utwórz backup przed zmianami.",
                "Uruchom testy przed refaktoryzacją.",
                "Wprowadzaj zmiany małymi krokami.",
                "Wykonaj rollback przy regresji.",
            ],
            expected_outcomes=[
                "Mniejsze sprzężenie.",
                "Wyższa spójność modułów.",
                "Łatwiejsze testowanie.",
                "Niższy koszt dalszego rozwoju.",
            ],
            priority=plan.priority,
            estimated_risk=plan.estimated_risk,
            estimated_roi=plan.estimated_roi,
            metadata={
                "source": "module_split_planner",
                "proposed_modules": list(plan.proposed_modules),
            },
        )

    def build_batch(
        self,
        plans: list[ModuleSplitPlan],
    ) -> list[RefactorBlueprint]:
        blueprints = [
            self.from_split_plan(plan)
            for plan in plans
        ]

        return sorted(
            blueprints,
            key=lambda item: (
                0 if item.priority == "high" else 1,
                -item.estimated_roi,
                item.estimated_risk,
                item.title,
            ),
        )

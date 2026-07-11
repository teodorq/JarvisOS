from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionStep:
    step_id: str
    name: str
    description: str
    order: int
    required: bool = True
    status: str = "PENDING"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskExecutionPlan:
    success: bool
    status: str
    task_id: str = ""
    target: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    requires_approval: bool = True
    safe_mode: bool = True
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [
            step.to_dict()
            for step in self.steps
        ]
        return data


class TaskExecutionPlanner:
    """
    Rozbija zadanie AutoDev na małe, bezpieczne kroki.

    Moduł:
    - nie zapisuje kodu,
    - nie wykonuje patchy,
    - nie zatwierdza zmian.
    """

    def __init__(self) -> None:
        self.last_plan: TaskExecutionPlan | None = None

    def build_plan(
        self,
        task: dict[str, Any],
    ) -> TaskExecutionPlan:

        if not isinstance(task, dict):
            return self._finish(
                TaskExecutionPlan(
                    success=False,
                    status="INVALID_TASK",
                    errors=[
                        "Zadanie musi być słownikiem."
                    ],
                )
            )

        task_id = str(
            task.get(
                "task_id",
                "",
            )
        ).strip()

        target = str(
            task.get(
                "target",
                "",
            )
        ).strip()

        title = str(
            task.get(
                "title",
                task.get(
                    "description",
                    "",
                ),
            )
        ).strip()

        errors: list[str] = []

        if not target:
            errors.append(
                "Brak pliku docelowego."
            )

        if not title:
            errors.append(
                "Brak opisu zadania."
            )

        if errors:
            return self._finish(
                TaskExecutionPlan(
                    success=False,
                    status="TASK_INCOMPLETE",
                    task_id=task_id,
                    target=target,
                    errors=errors,
                )
            )

        steps = [
            ExecutionStep(
                step_id="analyze",
                name="Analyze",
                description=(
                    "Przeanalizuj cel, kod i zależności."
                ),
                order=1,
            ),
            ExecutionStep(
                step_id="predict",
                name="Predict impact",
                description=(
                    "Oceń wpływ zmiany i ryzyko regresji."
                ),
                order=2,
            ),
            ExecutionStep(
                step_id="generate",
                name="Generate proposal",
                description=(
                    "Przygotuj propozycję zmiany bez zapisu."
                ),
                order=3,
            ),
            ExecutionStep(
                step_id="validate",
                name="Validate proposal",
                description=(
                    "Sprawdź składnię, bezpieczeństwo i diff."
                ),
                order=4,
            ),
            ExecutionStep(
                step_id="preview",
                name="Preview",
                description=(
                    "Pokaż podgląd i poczekaj na akceptację."
                ),
                order=5,
            ),
            ExecutionStep(
                step_id="execute",
                name="Execute",
                description=(
                    "Wykonaj zmianę dopiero po akceptacji."
                ),
                order=6,
                metadata={
                    "requires_approval": True,
                    "auto_rollback": True,
                },
            ),
            ExecutionStep(
                step_id="verify",
                name="Verify",
                description=(
                    "Uruchom testy i walidację końcową."
                ),
                order=7,
            ),
            ExecutionStep(
                step_id="learn",
                name="Learn",
                description=(
                    "Zapisz wynik i wnioski do pamięci."
                ),
                order=8,
            ),
        ]

        return self._finish(
            TaskExecutionPlan(
                success=True,
                status="PLAN_READY",
                task_id=task_id,
                target=target,
                steps=steps,
                requires_approval=True,
                safe_mode=True,
            )
        )

    def _finish(
        self,
        plan: TaskExecutionPlan,
    ) -> TaskExecutionPlan:

        self.last_plan = plan
        return plan

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_plan": (
                self.last_plan.to_dict()
                if self.last_plan is not None
                else None
            ),
        }

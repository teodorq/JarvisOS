from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class ImprovementPlanStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImprovementPlanStepType(str, Enum):
    ANALYZE = "ANALYZE"
    RESEARCH = "RESEARCH"
    REASON = "REASON"
    DESIGN = "DESIGN"
    PREPARE_PATCH = "PREPARE_PATCH"
    REVIEW = "REVIEW"
    APPROVE = "APPROVE"
    BACKUP = "BACKUP"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    ROLLBACK = "ROLLBACK"
    REPORT = "REPORT"


@dataclass
class ImprovementPlanStep:
    step_id: str
    name: str
    description: str
    step_type: str
    order: int
    dependencies: list[str]
    status: str
    requires_approval: bool
    estimated_effort: float
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImprovementPlanResult:
    plan_id: str
    improvement_id: str
    title: str
    status: str
    objective: str
    strategy: str
    steps: list[dict[str, Any]]
    execution_order: list[str]
    requires_approval: bool
    estimated_total_effort: float
    risks: list[str]
    success_criteria: list[str]
    rollback_required: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImprovementPlanner:

    def build(
        self,
        improvement: dict[str, Any],
        research_context: dict[str, Any] | None = None,
        reasoning_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_improvement = self._normalize_improvement(
            improvement
        )

        normalized_research = self._safe_dict(
            research_context
        )

        normalized_reasoning = self._safe_dict(
            reasoning_context
        )

        normalized_project = self._safe_dict(
            project_context
        )

        strategy = self._select_strategy(
            normalized_improvement
        )

        steps = self._build_steps(
            improvement=normalized_improvement,
            strategy=strategy,
            research_context=normalized_research,
            reasoning_context=normalized_reasoning,
            project_context=normalized_project,
        )

        steps = self._link_dependencies(
            steps
        )

        requires_approval = any(
            step.requires_approval
            for step in steps
        )

        rollback_required = self._rollback_required(
            normalized_improvement,
            normalized_project,
        )

        risks = self._collect_risks(
            normalized_improvement,
            steps,
        )

        success_criteria = self._build_success_criteria(
            normalized_improvement
        )

        blocked_reasons = self._find_blockers(
            normalized_improvement,
            normalized_research,
            normalized_reasoning,
        )

        status = (
            ImprovementPlanStatus.BLOCKED.value
            if blocked_reasons
            else (
                ImprovementPlanStatus.APPROVAL_REQUIRED.value
                if requires_approval
                else ImprovementPlanStatus.READY.value
            )
        )

        result = ImprovementPlanResult(
            plan_id=f"improvement_plan_{uuid4().hex}",
            improvement_id=normalized_improvement[
                "improvement_id"
            ],
            title=normalized_improvement[
                "title"
            ],
            status=status,
            objective=normalized_improvement[
                "description"
            ],
            strategy=strategy,
            steps=[
                step.to_dict()
                for step in steps
            ],
            execution_order=[
                step.step_id
                for step in sorted(
                    steps,
                    key=lambda item: item.order,
                )
            ],
            requires_approval=requires_approval,
            estimated_total_effort=round(
                sum(
                    step.estimated_effort
                    for step in steps
                ),
                2,
            ),
            risks=risks,
            success_criteria=success_criteria,
            rollback_required=rollback_required,
            metadata={
                "planner_version": "1.0.0",
                "blocked_reasons": blocked_reasons,
                "improvement_type": (
                    normalized_improvement[
                        "improvement_type"
                    ]
                ),
                "severity": normalized_improvement[
                    "severity"
                ],
                "affected_files": (
                    normalized_improvement[
                        "affected_files"
                    ]
                ),
                "affected_modules": (
                    normalized_improvement[
                        "affected_modules"
                    ]
                ),
                "research_available": bool(
                    normalized_research
                ),
                "reasoning_available": bool(
                    normalized_reasoning
                ),
            },
        )

        return result.to_dict()

    def create_plan(
        self,
        improvement: dict[str, Any],
        research_context: dict[str, Any] | None = None,
        reasoning_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.build(
            improvement=improvement,
            research_context=research_context,
            reasoning_context=reasoning_context,
            project_context=project_context,
        )

    def plan(
        self,
        improvement: dict[str, Any],
        research_context: dict[str, Any] | None = None,
        reasoning_context: dict[str, Any] | None = None,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.build(
            improvement=improvement,
            research_context=research_context,
            reasoning_context=reasoning_context,
            project_context=project_context,
        )

    def _build_steps(
        self,
        improvement: dict[str, Any],
        strategy: str,
        research_context: dict[str, Any],
        reasoning_context: dict[str, Any],
        project_context: dict[str, Any],
    ) -> list[ImprovementPlanStep]:

        steps: list[ImprovementPlanStep] = []

        order = 1

        steps.append(
            self._make_step(
                name="Analiza ulepszenia",
                description=(
                    "Przeanalizować wykryte ulepszenie, "
                    "jego wpływ oraz zakres zmian."
                ),
                step_type=(
                    ImprovementPlanStepType.ANALYZE
                ),
                order=order,
                estimated_effort=1.0,
                requires_approval=False,
                inputs={
                    "improvement": improvement,
                    "project_context": project_context,
                },
                risks=[
                    "Niepełny zakres analizy.",
                ],
            )
        )

        order += 1

        if not research_context:
            steps.append(
                self._make_step(
                    name="Research techniczny",
                    description=(
                        "Przeprowadzić research kodu, "
                        "zależności i możliwych rozwiązań."
                    ),
                    step_type=(
                        ImprovementPlanStepType.RESEARCH
                    ),
                    order=order,
                    estimated_effort=1.5,
                    requires_approval=False,
                    inputs={
                        "improvement": improvement,
                    },
                    risks=[
                        "Niepełny kontekst projektu.",
                    ],
                )
            )

            order += 1

        if not reasoning_context:
            steps.append(
                self._make_step(
                    name="Ocena strategii",
                    description=(
                        "Porównać możliwe strategie "
                        "i wybrać rozwiązanie o najlepszym "
                        "stosunku ryzyka do korzyści."
                    ),
                    step_type=(
                        ImprovementPlanStepType.REASON
                    ),
                    order=order,
                    estimated_effort=1.0,
                    requires_approval=False,
                    inputs={
                        "improvement": improvement,
                        "strategy": strategy,
                    },
                    risks=[
                        "Błędna ocena ryzyka.",
                    ],
                )
            )

            order += 1

        steps.append(
            self._make_step(
                name="Projekt techniczny",
                description=(
                    "Przygotować dokładny projekt zmian, "
                    "listę plików i plan bezpiecznego wykonania."
                ),
                step_type=(
                    ImprovementPlanStepType.DESIGN
                ),
                order=order,
                estimated_effort=1.5,
                requires_approval=False,
                inputs={
                    "research_context": research_context,
                    "reasoning_context": reasoning_context,
                    "affected_files": improvement[
                        "affected_files"
                    ],
                },
                risks=[
                    "Pominięcie zależności między modułami.",
                ],
            )
        )

        order += 1

        steps.append(
            self._make_step(
                name="Przygotowanie patcha",
                description=(
                    "Wygenerować patch i podgląd zmian "
                    "bez modyfikowania projektu."
                ),
                step_type=(
                    ImprovementPlanStepType.PREPARE_PATCH
                ),
                order=order,
                estimated_effort=2.5,
                requires_approval=False,
                inputs={
                    "improvement": improvement,
                    "strategy": strategy,
                },
                risks=[
                    "Patch może obejmować niezamierzone zmiany.",
                ],
            )
        )

        order += 1

        steps.append(
            self._make_step(
                name="Przegląd patcha",
                description=(
                    "Sprawdzić zakres, zgodność, ryzyko "
                    "oraz możliwość rollbacku."
                ),
                step_type=(
                    ImprovementPlanStepType.REVIEW
                ),
                order=order,
                estimated_effort=1.0,
                requires_approval=False,
                risks=[
                    "Niewykrycie błędu przed wykonaniem.",
                ],
            )
        )

        order += 1

        approval_required = self._approval_required(
            improvement
        )

        if approval_required:
            steps.append(
                self._make_step(
                    name="Akceptacja zmian",
                    description=(
                        "Uzyskać zgodę na wykonanie patcha."
                    ),
                    step_type=(
                        ImprovementPlanStepType.APPROVE
                    ),
                    order=order,
                    estimated_effort=0.25,
                    requires_approval=True,
                    risks=[
                        "Wykonanie bez wymaganej zgody.",
                    ],
                )
            )

            order += 1

        steps.append(
            self._make_step(
                name="Backup projektu",
                description=(
                    "Utworzyć backup plików objętych zmianą."
                ),
                step_type=(
                    ImprovementPlanStepType.BACKUP
                ),
                order=order,
                estimated_effort=0.5,
                requires_approval=False,
                risks=[
                    "Niekompletny backup.",
                ],
            )
        )

        order += 1

        steps.append(
            self._make_step(
                name="Wykonanie zmian",
                description=(
                    "Zastosować zaakceptowany patch "
                    "przez DeveloperController."
                ),
                step_type=(
                    ImprovementPlanStepType.EXECUTE
                ),
                order=order,
                estimated_effort=2.0,
                requires_approval=approval_required,
                risks=[
                    "Możliwość wprowadzenia regresji.",
                    "Możliwość uszkodzenia zależnych modułów.",
                ],
            )
        )

        order += 1

        steps.append(
            self._make_step(
                name="Walidacja zmian",
                description=(
                    "Uruchomić walidację składni, importów, "
                    "testów i zachowania funkcjonalnego."
                ),
                step_type=(
                    ImprovementPlanStepType.VALIDATE
                ),
                order=order,
                estimated_effort=2.0,
                requires_approval=False,
                risks=[
                    "Niewystarczające pokrycie testami.",
                ],
            )
        )

        order += 1

        steps.append(
            self._make_step(
                name="Rollback awaryjny",
                description=(
                    "Przywrócić backup, jeżeli walidacja "
                    "wykryje błąd blokujący."
                ),
                step_type=(
                    ImprovementPlanStepType.ROLLBACK
                ),
                order=order,
                estimated_effort=0.75,
                requires_approval=False,
                risks=[
                    "Rollback może być niepełny.",
                ],
                metadata={
                    "conditional": True,
                    "condition": (
                        "validation_failed"
                    ),
                },
            )
        )

        order += 1

        steps.append(
            self._make_step(
                name="Raport końcowy",
                description=(
                    "Przygotować raport wykonania, "
                    "walidacji i dalszych rekomendacji."
                ),
                step_type=(
                    ImprovementPlanStepType.REPORT
                ),
                order=order,
                estimated_effort=0.5,
                requires_approval=False,
                risks=[],
            )
        )

        return steps

    def _link_dependencies(
        self,
        steps: list[ImprovementPlanStep],
    ) -> list[ImprovementPlanStep]:

        ordered = sorted(
            steps,
            key=lambda item: item.order,
        )

        previous_step_id: str | None = None

        for step in ordered:
            if previous_step_id is None:
                step.dependencies = []
                step.status = "READY"

            else:
                step.dependencies = [
                    previous_step_id
                ]
                step.status = "BLOCKED"

            previous_step_id = step.step_id

        return ordered

    def _make_step(
        self,
        name: str,
        description: str,
        step_type: ImprovementPlanStepType,
        order: int,
        estimated_effort: float,
        requires_approval: bool,
        inputs: dict[str, Any] | None = None,
        risks: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ImprovementPlanStep:

        return ImprovementPlanStep(
            step_id=f"improvement_step_{uuid4().hex}",
            name=name,
            description=description,
            step_type=step_type.value,
            order=max(
                1,
                int(order),
            ),
            dependencies=[],
            status="PENDING",
            requires_approval=bool(
                requires_approval
            ),
            estimated_effort=max(
                0.0,
                float(estimated_effort),
            ),
            inputs=self._safe_dict(
                inputs
            ),
            outputs={},
            risks=self._unique_strings(
                risks or []
            ),
            metadata={
                "planner_version": "1.0.0",
                **(metadata or {}),
            },
        )

    def _select_strategy(
        self,
        improvement: dict[str, Any],
    ) -> str:

        improvement_type = improvement[
            "improvement_type"
        ]

        severity = improvement[
            "severity"
        ]

        if improvement_type == "SECURITY":
            return "SECURITY_FIRST"

        if severity == "CRITICAL":
            return "MINIMAL_SAFE_PATCH"

        if improvement_type in {
            "ARCHITECTURE",
            "REFACTOR",
        }:
            return "INCREMENTAL_REFACTOR"

        if improvement_type == "PERFORMANCE":
            return "MEASURE_OPTIMIZE_VALIDATE"

        if improvement_type == "TESTING":
            return "TEST_FIRST"

        return "SAFE_INCREMENTAL_CHANGE"

    def _approval_required(
        self,
        improvement: dict[str, Any],
    ) -> bool:

        if improvement[
            "severity"
        ] in {
            "HIGH",
            "CRITICAL",
        }:
            return True

        if improvement[
            "improvement_type"
        ] in {
            "SECURITY",
            "ARCHITECTURE",
        }:
            return True

        if len(
            improvement[
                "affected_files"
            ]
        ) > 3:
            return True

        if len(
            improvement[
                "affected_modules"
            ]
        ) > 1:
            return True

        return False

    def _rollback_required(
        self,
        improvement: dict[str, Any],
        project_context: dict[str, Any],
    ) -> bool:

        if project_context.get(
            "rollback_required"
        ) is True:
            return True

        return (
            improvement["severity"]
            in {
                "HIGH",
                "CRITICAL",
            }
            or improvement[
                "improvement_type"
            ]
            in {
                "SECURITY",
                "ARCHITECTURE",
                "REFACTOR",
            }
            or len(
                improvement[
                    "affected_files"
                ]
            )
            > 1
        )

    def _collect_risks(
        self,
        improvement: dict[str, Any],
        steps: list[ImprovementPlanStep],
    ) -> list[str]:

        risks: list[str] = []

        risks.extend(
            improvement[
                "risks"
            ]
        )

        for step in steps:
            risks.extend(
                step.risks
            )

        return self._unique_strings(
            risks
        )

    def _build_success_criteria(
        self,
        improvement: dict[str, Any],
    ) -> list[str]:

        criteria = [
            "Patch został zastosowany bez błędów.",
            "Walidacja składni zakończyła się sukcesem.",
            "Walidacja importów zakończyła się sukcesem.",
            "Nie wykryto krytycznych regresji.",
            "Backup i rollback są dostępne.",
        ]

        improvement_type = improvement[
            "improvement_type"
        ]

        if improvement_type == "BUG_FIX":
            criteria.append(
                "Pierwotny błąd nie występuje."
            )

        elif improvement_type == "PERFORMANCE":
            criteria.append(
                "Wydajność po zmianie jest lepsza lub nie gorsza."
            )

        elif improvement_type == "SECURITY":
            criteria.append(
                "Wykryte ryzyko bezpieczeństwa zostało usunięte."
            )

        elif improvement_type == "TESTING":
            criteria.append(
                "Dodane testy przechodzą poprawnie."
            )

        elif improvement_type == "DOCUMENTATION":
            criteria.append(
                "Dokumentacja odpowiada aktualnemu kodowi."
            )

        return self._unique_strings(
            criteria
        )

    def _find_blockers(
        self,
        improvement: dict[str, Any],
        research_context: dict[str, Any],
        reasoning_context: dict[str, Any],
    ) -> list[str]:

        blockers: list[str] = []

        if not improvement[
            "description"
        ]:
            blockers.append(
                "Brak opisu ulepszenia."
            )

        if (
            improvement[
                "improvement_type"
            ]
            == "UNKNOWN"
            and not research_context
        ):
            blockers.append(
                "Nieznany typ ulepszenia wymaga researchu."
            )

        if (
            improvement[
                "severity"
            ]
            in {
                "HIGH",
                "CRITICAL",
            }
            and not reasoning_context
        ):
            blockers.append(
                "Ulepszenie wysokiego ryzyka wymaga analizy Reasonera."
            )

        return self._unique_strings(
            blockers
        )

    def _normalize_improvement(
        self,
        improvement: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(
            improvement,
            dict,
        ):
            raise TypeError(
                "ImprovementPlanner wymaga improvement typu dict."
            )

        return {
            "improvement_id": str(
                improvement.get(
                    "improvement_id",
                    f"improvement_{uuid4().hex}",
                )
            ),
            "title": str(
                improvement.get(
                    "title",
                    improvement.get(
                        "name",
                        "Nieznane ulepszenie",
                    ),
                )
            ).strip(),
            "description": str(
                improvement.get(
                    "description",
                    improvement.get(
                        "details",
                        "",
                    ),
                )
            ).strip(),
            "improvement_type": str(
                improvement.get(
                    "improvement_type",
                    "UNKNOWN",
                )
            ).upper(),
            "severity": str(
                improvement.get(
                    "severity",
                    "MEDIUM",
                )
            ).upper(),
            "score": self._safe_float(
                improvement.get(
                    "score",
                    0.0,
                ),
                0.0,
            ),
            "confidence": self._safe_float(
                improvement.get(
                    "confidence",
                    0.0,
                ),
                0.0,
            ),
            "affected_files": self._safe_string_list(
                improvement.get(
                    "affected_files",
                    [],
                )
            ),
            "affected_modules": self._safe_string_list(
                improvement.get(
                    "affected_modules",
                    [],
                )
            ),
            "risks": self._safe_string_list(
                improvement.get(
                    "risks",
                    [],
                )
            ),
            "benefits": self._safe_string_list(
                improvement.get(
                    "benefits",
                    [],
                )
            ),
            "recommended_actions": (
                self._safe_string_list(
                    improvement.get(
                        "recommended_actions",
                        [],
                    )
                )
            ),
            "metadata": self._safe_dict(
                improvement.get(
                    "metadata",
                    {},
                )
            ),
        }

    def _safe_float(
        self,
        value: Any,
        default: float,
    ) -> float:

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(value)

        return {}

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(value, list):
            return list(value)

        if isinstance(value, tuple):
            return list(value)

        if isinstance(value, set):
            return list(value)

        if value is None:
            return []

        return [value]

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        return self._unique_strings(
            self._safe_list(value)
        )

    def _unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            text = str(value).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(text)

        return result

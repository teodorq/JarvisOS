from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class DecompositionStrategy(str, Enum):
    PHASE_BASED = "PHASE_BASED"
    FEATURE_BASED = "FEATURE_BASED"
    RISK_BASED = "RISK_BASED"
    DEPENDENCY_BASED = "DEPENDENCY_BASED"
    MILESTONE_BASED = "MILESTONE_BASED"
    HYBRID = "HYBRID"


class SubGoalType(str, Enum):
    ANALYSIS = "ANALYSIS"
    RESEARCH = "RESEARCH"
    DESIGN = "DESIGN"
    IMPLEMENTATION = "IMPLEMENTATION"
    INTEGRATION = "INTEGRATION"
    VALIDATION = "VALIDATION"
    TESTING = "TESTING"
    DOCUMENTATION = "DOCUMENTATION"
    DEPLOYMENT = "DEPLOYMENT"
    REVIEW = "REVIEW"
    MAINTENANCE = "MAINTENANCE"
    UNKNOWN = "UNKNOWN"


class SubGoalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass
class SubGoalProposal:
    proposal_id: str
    title: str
    description: str
    subgoal_type: str
    priority: str
    order: int
    estimated_effort: float
    dependencies: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    status: str = SubGoalStatus.PROPOSED.value
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalDecompositionResult:
    decomposition_id: str
    source_goal: dict[str, Any]
    strategy: str
    subgoals: list[dict[str, Any]]
    execution_order: list[str]
    estimated_total_effort: float
    complexity_score: float
    confidence: float
    warnings: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoalDecomposer:

    COMPLEXITY_KEYWORDS = {
        "HIGH": {
            "cały projekt",
            "architektura",
            "system",
            "core",
            "silnik",
            "platforma",
            "multi-agent",
            "self improvement",
            "continuous",
            "pełna integracja",
            "wiele modułów",
            "przebudowa",
        },
        "MEDIUM": {
            "moduł",
            "integracja",
            "workflow",
            "pipeline",
            "controller",
            "service",
            "router",
            "refaktor",
            "feature",
            "funkcja",
        },
        "LOW": {
            "plik",
            "funkcja",
            "metoda",
            "literówka",
            "komunikat",
            "mała zmiana",
        },
    }

    STRATEGY_PHASES = {
        DecompositionStrategy.PHASE_BASED: [
            SubGoalType.ANALYSIS,
            SubGoalType.DESIGN,
            SubGoalType.IMPLEMENTATION,
            SubGoalType.INTEGRATION,
            SubGoalType.TESTING,
            SubGoalType.DOCUMENTATION,
        ],
        DecompositionStrategy.FEATURE_BASED: [
            SubGoalType.ANALYSIS,
            SubGoalType.DESIGN,
            SubGoalType.IMPLEMENTATION,
            SubGoalType.TESTING,
            SubGoalType.REVIEW,
        ],
        DecompositionStrategy.RISK_BASED: [
            SubGoalType.ANALYSIS,
            SubGoalType.RESEARCH,
            SubGoalType.DESIGN,
            SubGoalType.IMPLEMENTATION,
            SubGoalType.VALIDATION,
            SubGoalType.REVIEW,
        ],
        DecompositionStrategy.DEPENDENCY_BASED: [
            SubGoalType.ANALYSIS,
            SubGoalType.RESEARCH,
            SubGoalType.DESIGN,
            SubGoalType.IMPLEMENTATION,
            SubGoalType.INTEGRATION,
            SubGoalType.TESTING,
        ],
        DecompositionStrategy.MILESTONE_BASED: [
            SubGoalType.ANALYSIS,
            SubGoalType.DESIGN,
            SubGoalType.IMPLEMENTATION,
            SubGoalType.INTEGRATION,
            SubGoalType.TESTING,
            SubGoalType.DEPLOYMENT,
        ],
        DecompositionStrategy.HYBRID: [
            SubGoalType.ANALYSIS,
            SubGoalType.RESEARCH,
            SubGoalType.DESIGN,
            SubGoalType.IMPLEMENTATION,
            SubGoalType.INTEGRATION,
            SubGoalType.TESTING,
            SubGoalType.VALIDATION,
            SubGoalType.DOCUMENTATION,
        ],
    }

    def decompose(
        self,
        goal: dict[str, Any],
        strategy: str | None = None,
        context: dict[str, Any] | None = None,
        max_subgoals: int = 12,
    ) -> dict[str, Any]:

        normalized_goal = self._normalize_goal(goal)
        normalized_context = self._normalize_context(context)

        complexity_score = self._calculate_complexity(
            normalized_goal,
            normalized_context,
        )

        selected_strategy = self._select_strategy(
            goal=normalized_goal,
            requested_strategy=strategy,
            complexity_score=complexity_score,
            context=normalized_context,
        )

        phase_types = list(
            self.STRATEGY_PHASES[selected_strategy]
        )

        phase_types = self._adjust_phases(
            phase_types=phase_types,
            goal=normalized_goal,
            context=normalized_context,
            complexity_score=complexity_score,
        )

        proposals = self._build_proposals(
            goal=normalized_goal,
            phase_types=phase_types,
            context=normalized_context,
            complexity_score=complexity_score,
        )

        proposals = proposals[:max(
            1,
            int(max_subgoals),
        )]

        proposals = self._link_dependencies(
            proposals
        )

        warnings = self._build_warnings(
            goal=normalized_goal,
            proposals=proposals,
            complexity_score=complexity_score,
            context=normalized_context,
        )

        confidence = self._calculate_confidence(
            goal=normalized_goal,
            proposals=proposals,
            context=normalized_context,
        )

        result = GoalDecompositionResult(
            decomposition_id=(
                f"goal_decomposition_{uuid4().hex}"
            ),
            source_goal=normalized_goal,
            strategy=selected_strategy.value,
            subgoals=[
                proposal.to_dict()
                for proposal in proposals
            ],
            execution_order=[
                proposal.proposal_id
                for proposal in sorted(
                    proposals,
                    key=lambda item: item.order,
                )
            ],
            estimated_total_effort=round(
                sum(
                    proposal.estimated_effort
                    for proposal in proposals
                ),
                2,
            ),
            complexity_score=round(
                complexity_score,
                2,
            ),
            confidence=confidence,
            warnings=warnings,
            metadata={
                "decomposer_version": "1.0.0",
                "subgoals_count": len(proposals),
                "context_available": bool(
                    normalized_context
                ),
                "goal_type": normalized_goal[
                    "goal_type"
                ],
                "timeframe": normalized_goal[
                    "timeframe"
                ],
            },
        )

        return result.to_dict()

    def build(
        self,
        goal: dict[str, Any],
        strategy: str | None = None,
        context: dict[str, Any] | None = None,
        max_subgoals: int = 12,
    ) -> dict[str, Any]:

        return self.decompose(
            goal=goal,
            strategy=strategy,
            context=context,
            max_subgoals=max_subgoals,
        )

    def analyze(
        self,
        goal: dict[str, Any],
        strategy: str | None = None,
        context: dict[str, Any] | None = None,
        max_subgoals: int = 12,
    ) -> dict[str, Any]:

        return self.decompose(
            goal=goal,
            strategy=strategy,
            context=context,
            max_subgoals=max_subgoals,
        )

    def _select_strategy(
        self,
        goal: dict[str, Any],
        requested_strategy: str | None,
        complexity_score: float,
        context: dict[str, Any],
    ) -> DecompositionStrategy:

        if requested_strategy is not None:
            normalized = str(
                requested_strategy
            ).strip().upper()

            for strategy in DecompositionStrategy:
                if strategy.value == normalized:
                    return strategy

        goal_type = goal["goal_type"]
        timeframe = goal["timeframe"]

        if context.get(
            "high_risk",
            False,
        ):
            return DecompositionStrategy.RISK_BASED

        if context.get(
            "dependency_count",
            0,
        ) and self._safe_int(
            context.get(
                "dependency_count",
                0,
            ),
            0,
        ) >= 5:
            return DecompositionStrategy.DEPENDENCY_BASED

        if goal_type in {
            "FEATURE",
            "PROJECT",
        }:
            if complexity_score >= 70.0:
                return DecompositionStrategy.HYBRID

            return DecompositionStrategy.FEATURE_BASED

        if goal_type in {
            "REFACTOR",
            "MAINTENANCE",
        }:
            return DecompositionStrategy.RISK_BASED

        if timeframe in {
            "LONG_TERM",
            "CONTINUOUS",
        }:
            return DecompositionStrategy.MILESTONE_BASED

        return DecompositionStrategy.PHASE_BASED

    def _adjust_phases(
        self,
        phase_types: list[SubGoalType],
        goal: dict[str, Any],
        context: dict[str, Any],
        complexity_score: float,
    ) -> list[SubGoalType]:

        adjusted = list(phase_types)

        if (
            goal["goal_type"]
            in {
                "RESEARCH",
                "LEARNING",
            }
            and SubGoalType.RESEARCH
            not in adjusted
        ):
            adjusted.insert(
                1,
                SubGoalType.RESEARCH,
            )

        if (
            context.get(
                "requires_deployment",
                False,
            )
            and SubGoalType.DEPLOYMENT
            not in adjusted
        ):
            adjusted.append(
                SubGoalType.DEPLOYMENT
            )

        if (
            context.get(
                "requires_documentation",
                True,
            )
            and SubGoalType.DOCUMENTATION
            not in adjusted
        ):
            adjusted.append(
                SubGoalType.DOCUMENTATION
            )

        if (
            complexity_score < 30.0
            and len(adjusted) > 5
        ):
            adjusted = [
                phase
                for phase in adjusted
                if phase
                not in {
                    SubGoalType.RESEARCH,
                    SubGoalType.DOCUMENTATION,
                }
            ]

        return self._unique_phases(
            adjusted
        )

    def _build_proposals(
        self,
        goal: dict[str, Any],
        phase_types: list[SubGoalType],
        context: dict[str, Any],
        complexity_score: float,
    ) -> list[SubGoalProposal]:

        proposals: list[SubGoalProposal] = []

        for order, phase_type in enumerate(
            phase_types,
            start=1,
        ):
            title = self._phase_title(
                phase_type,
                goal,
            )

            description = self._phase_description(
                phase_type,
                goal,
            )

            effort = self._estimate_phase_effort(
                phase_type=phase_type,
                complexity_score=complexity_score,
                context=context,
            )

            priority = self._phase_priority(
                phase_type,
                goal["priority"],
            )

            success_criteria = (
                self._phase_success_criteria(
                    phase_type,
                    goal,
                )
            )

            risks = self._phase_risks(
                phase_type,
                context,
            )

            proposal = SubGoalProposal(
                proposal_id=f"subgoal_{uuid4().hex}",
                title=title,
                description=description,
                subgoal_type=phase_type.value,
                priority=priority,
                order=order,
                estimated_effort=effort,
                success_criteria=success_criteria,
                risks=risks,
                tags=self._build_tags(
                    goal,
                    phase_type,
                ),
                metadata={
                    "source_goal_id": goal[
                        "goal_id"
                    ],
                    "decomposer_version": "1.0.0",
                },
            )

            proposals.append(proposal)

        return proposals

    def _link_dependencies(
        self,
        proposals: list[SubGoalProposal],
    ) -> list[SubGoalProposal]:

        ordered = sorted(
            proposals,
            key=lambda item: item.order,
        )

        for index, proposal in enumerate(
            ordered
        ):
            if index == 0:
                proposal.dependencies = []
                proposal.status = (
                    SubGoalStatus.READY.value
                )
                continue

            previous = ordered[index - 1]

            proposal.dependencies = [
                previous.proposal_id
            ]
            proposal.status = (
                SubGoalStatus.BLOCKED.value
            )

        return ordered

    def _calculate_complexity(
        self,
        goal: dict[str, Any],
        context: dict[str, Any],
    ) -> float:

        score = 20.0
        text = (
            f"{goal['title']} "
            f"{goal['description']}"
        ).lower()

        for keyword in self.COMPLEXITY_KEYWORDS[
            "HIGH"
        ]:
            if keyword in text:
                score += 12.0

        for keyword in self.COMPLEXITY_KEYWORDS[
            "MEDIUM"
        ]:
            if keyword in text:
                score += 6.0

        for keyword in self.COMPLEXITY_KEYWORDS[
            "LOW"
        ]:
            if keyword in text:
                score += 2.0

        if goal["timeframe"] == "LONG_TERM":
            score += 15.0

        if goal["timeframe"] == "CONTINUOUS":
            score += 20.0

        if goal["priority"] == "CRITICAL":
            score += 10.0

        if goal["goal_type"] in {
            "PROJECT",
            "SELF_IMPROVEMENT",
            "OPERATIONS",
        }:
            score += 15.0

        dependency_count = self._safe_int(
            context.get(
                "dependency_count",
                0,
            ),
            0,
        )

        affected_modules = self._safe_int(
            context.get(
                "affected_modules",
                0,
            ),
            0,
        )

        score += min(
            20.0,
            dependency_count * 2.0,
        )

        score += min(
            20.0,
            affected_modules * 3.0,
        )

        return max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

    def _estimate_phase_effort(
        self,
        phase_type: SubGoalType,
        complexity_score: float,
        context: dict[str, Any],
    ) -> float:

        base_effort = {
            SubGoalType.ANALYSIS: 1.0,
            SubGoalType.RESEARCH: 1.5,
            SubGoalType.DESIGN: 2.0,
            SubGoalType.IMPLEMENTATION: 4.0,
            SubGoalType.INTEGRATION: 2.5,
            SubGoalType.VALIDATION: 1.5,
            SubGoalType.TESTING: 2.0,
            SubGoalType.DOCUMENTATION: 1.0,
            SubGoalType.DEPLOYMENT: 1.5,
            SubGoalType.REVIEW: 1.0,
            SubGoalType.MAINTENANCE: 1.5,
            SubGoalType.UNKNOWN: 1.0,
        }

        multiplier = 1.0

        if complexity_score >= 75.0:
            multiplier = 2.0

        elif complexity_score >= 50.0:
            multiplier = 1.5

        elif complexity_score < 25.0:
            multiplier = 0.75

        if context.get(
            "limited_resources",
            False,
        ):
            multiplier += 0.25

        return round(
            base_effort.get(
                phase_type,
                1.0,
            )
            * multiplier,
            2,
        )

    def _phase_priority(
        self,
        phase_type: SubGoalType,
        goal_priority: str,
    ) -> str:

        if phase_type in {
            SubGoalType.ANALYSIS,
            SubGoalType.DESIGN,
            SubGoalType.IMPLEMENTATION,
            SubGoalType.TESTING,
            SubGoalType.VALIDATION,
        }:
            return goal_priority

        if goal_priority == "CRITICAL":
            return "HIGH"

        if goal_priority == "HIGH":
            return "MEDIUM"

        return "LOW"

    def _phase_title(
        self,
        phase_type: SubGoalType,
        goal: dict[str, Any],
    ) -> str:

        base_title = goal["title"]

        titles = {
            SubGoalType.ANALYSIS: (
                f"Przeanalizować cel: {base_title}"
            ),
            SubGoalType.RESEARCH: (
                f"Przeprowadzić research: {base_title}"
            ),
            SubGoalType.DESIGN: (
                f"Zaprojektować rozwiązanie: {base_title}"
            ),
            SubGoalType.IMPLEMENTATION: (
                f"Zaimplementować rozwiązanie: {base_title}"
            ),
            SubGoalType.INTEGRATION: (
                f"Zintegrować rozwiązanie: {base_title}"
            ),
            SubGoalType.VALIDATION: (
                f"Zweryfikować rozwiązanie: {base_title}"
            ),
            SubGoalType.TESTING: (
                f"Przetestować rozwiązanie: {base_title}"
            ),
            SubGoalType.DOCUMENTATION: (
                f"Udokumentować rozwiązanie: {base_title}"
            ),
            SubGoalType.DEPLOYMENT: (
                f"Wdrożyć rozwiązanie: {base_title}"
            ),
            SubGoalType.REVIEW: (
                f"Przeprowadzić przegląd: {base_title}"
            ),
            SubGoalType.MAINTENANCE: (
                f"Zaplanować utrzymanie: {base_title}"
            ),
            SubGoalType.UNKNOWN: (
                f"Zrealizować etap: {base_title}"
            ),
        }

        return titles[phase_type]

    def _phase_description(
        self,
        phase_type: SubGoalType,
        goal: dict[str, Any],
    ) -> str:

        descriptions = {
            SubGoalType.ANALYSIS: (
                "Określić zakres, ograniczenia, zależności "
                "i kryteria sukcesu celu."
            ),
            SubGoalType.RESEARCH: (
                "Zebrać brakujące informacje, przeanalizować "
                "projekt i porównać możliwe podejścia."
            ),
            SubGoalType.DESIGN: (
                "Przygotować architekturę, interfejsy "
                "oraz plan techniczny wykonania."
            ),
            SubGoalType.IMPLEMENTATION: (
                "Wykonać właściwe zmiany potrzebne "
                "do osiągnięcia celu."
            ),
            SubGoalType.INTEGRATION: (
                "Połączyć nowe rozwiązanie z istniejącymi "
                "modułami i workflow."
            ),
            SubGoalType.VALIDATION: (
                "Sprawdzić poprawność, zgodność i bezpieczeństwo "
                "uzyskanego rozwiązania."
            ),
            SubGoalType.TESTING: (
                "Uruchomić testy jednostkowe, integracyjne "
                "i funkcjonalne."
            ),
            SubGoalType.DOCUMENTATION: (
                "Zapisać architekturę, zmiany, instrukcje "
                "i aktualny checkpoint."
            ),
            SubGoalType.DEPLOYMENT: (
                "Przygotować i wykonać bezpieczne wdrożenie."
            ),
            SubGoalType.REVIEW: (
                "Ocenić rezultat, ryzyko, jakość "
                "i gotowość do zakończenia."
            ),
            SubGoalType.MAINTENANCE: (
                "Zaplanować dalsze utrzymanie, monitoring "
                "i rozwój rozwiązania."
            ),
            SubGoalType.UNKNOWN: (
                "Wykonać wymagany etap realizacji celu."
            ),
        }

        return (
            descriptions[phase_type]
            + " Cel źródłowy: "
            + goal["description"]
        ).strip()

    def _phase_success_criteria(
        self,
        phase_type: SubGoalType,
        goal: dict[str, Any],
    ) -> list[str]:

        criteria = {
            SubGoalType.ANALYSIS: [
                "Zakres celu jest jednoznacznie opisany.",
                "Zależności i ograniczenia są znane.",
            ],
            SubGoalType.RESEARCH: [
                "Research zakończył się raportem.",
                "Zebrano wystarczający kontekst do decyzji.",
            ],
            SubGoalType.DESIGN: [
                "Powstał kompletny plan techniczny.",
                "Interfejsy i zależności są określone.",
            ],
            SubGoalType.IMPLEMENTATION: [
                "Kod lub rozwiązanie zostało przygotowane.",
                "Zakres implementacji odpowiada planowi.",
            ],
            SubGoalType.INTEGRATION: [
                "Rozwiązanie współpracuje z istniejącym systemem.",
                "Nie wykryto konfliktów integracyjnych.",
            ],
            SubGoalType.VALIDATION: [
                "Walidacja zakończyła się sukcesem.",
                "Nie wykryto błędów blokujących.",
            ],
            SubGoalType.TESTING: [
                "Wszystkie wymagane testy zakończyły się sukcesem.",
                "Nie wykryto krytycznych regresji.",
            ],
            SubGoalType.DOCUMENTATION: [
                "Dokumentacja została zaktualizowana.",
                "Checkpoint projektu jest kompletny.",
            ],
            SubGoalType.DEPLOYMENT: [
                "Wdrożenie zakończyło się sukcesem.",
                "Możliwy jest rollback.",
            ],
            SubGoalType.REVIEW: [
                "Rezultat został oceniony.",
                "Znane są dalsze działania.",
            ],
            SubGoalType.MAINTENANCE: [
                "Powstał plan utrzymania.",
                "Zdefiniowano monitoring i kolejne przeglądy.",
            ],
            SubGoalType.UNKNOWN: [
                "Etap został wykonany zgodnie z wymaganiami.",
            ],
        }

        result = list(
            criteria[phase_type]
        )

        if (
            phase_type
            == SubGoalType.VALIDATION
        ):
            result.extend(
                goal.get(
                    "success_criteria",
                    [],
                )
            )

        return self._unique_strings(
            result
        )

    def _phase_risks(
        self,
        phase_type: SubGoalType,
        context: dict[str, Any],
    ) -> list[str]:

        risks = {
            SubGoalType.ANALYSIS: [
                "Niepełny lub niejednoznaczny zakres.",
            ],
            SubGoalType.RESEARCH: [
                "Nieaktualne lub niekompletne dane.",
            ],
            SubGoalType.DESIGN: [
                "Błędne założenia architektoniczne.",
            ],
            SubGoalType.IMPLEMENTATION: [
                "Błędy implementacji i regresje.",
            ],
            SubGoalType.INTEGRATION: [
                "Konflikty między modułami.",
            ],
            SubGoalType.VALIDATION: [
                "Niewystarczająca walidacja.",
            ],
            SubGoalType.TESTING: [
                "Brak pokrycia ważnych scenariuszy.",
            ],
            SubGoalType.DOCUMENTATION: [
                "Dokumentacja może nie odpowiadać kodowi.",
            ],
            SubGoalType.DEPLOYMENT: [
                "Błąd wdrożenia lub brak rollbacku.",
            ],
            SubGoalType.REVIEW: [
                "Zbyt wczesne zaakceptowanie rezultatu.",
            ],
            SubGoalType.MAINTENANCE: [
                "Brak dalszego monitoringu.",
            ],
            SubGoalType.UNKNOWN: [
                "Nieznane ryzyko etapu.",
            ],
        }

        result = list(
            risks[phase_type]
        )

        if context.get(
            "high_risk",
            False,
        ):
            result.append(
                "Cel został oznaczony jako wysokiego ryzyka."
            )

        return self._unique_strings(
            result
        )

    def _build_tags(
        self,
        goal: dict[str, Any],
        phase_type: SubGoalType,
    ) -> list[str]:

        return self._unique_strings(
            [
                *goal.get(
                    "tags",
                    [],
                ),
                goal["goal_type"].lower(),
                phase_type.value.lower(),
                "long-term-planner",
            ]
        )

    def _build_warnings(
        self,
        goal: dict[str, Any],
        proposals: list[SubGoalProposal],
        complexity_score: float,
        context: dict[str, Any],
    ) -> list[str]:

        warnings: list[str] = []

        if complexity_score >= 80.0:
            warnings.append(
                "Cel ma bardzo wysoką złożoność."
            )

        if len(proposals) >= 10:
            warnings.append(
                "Plan zawiera dużą liczbę podcelów."
            )

        if not goal["success_criteria"]:
            warnings.append(
                "Cel źródłowy nie posiada własnych kryteriów sukcesu."
            )

        if context.get(
            "high_risk",
            False,
        ):
            warnings.append(
                "Wymagany jest dodatkowy przegląd ryzyka."
            )

        if goal["deadline"] is not None:
            warnings.append(
                "Należy uwzględnić termin końcowy celu."
            )

        return self._unique_strings(
            warnings
        )

    def _calculate_confidence(
        self,
        goal: dict[str, Any],
        proposals: list[SubGoalProposal],
        context: dict[str, Any],
    ) -> float:

        confidence = 0.65

        if goal["description"]:
            confidence += 0.08

        if goal["success_criteria"]:
            confidence += 0.08

        if context:
            confidence += 0.06

        if len(proposals) >= 4:
            confidence += 0.05

        if not goal["title"]:
            confidence -= 0.3

        return round(
            max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            2,
        )

    def _normalize_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(goal, dict):
            raise TypeError(
                "GoalDecomposer wymaga celu typu dict."
            )

        return {
            "goal_id": str(
                goal.get(
                    "goal_id",
                    f"goal_{uuid4().hex}",
                )
            ),
            "title": str(
                goal.get(
                    "title",
                    goal.get(
                        "goal",
                        "Nieznany cel",
                    ),
                )
            ).strip(),
            "description": str(
                goal.get(
                    "description",
                    goal.get(
                        "original_request",
                        "",
                    ),
                )
            ).strip(),
            "goal_type": str(
                goal.get(
                    "goal_type",
                    "UNKNOWN",
                )
            ).upper(),
            "priority": str(
                goal.get(
                    "priority",
                    "MEDIUM",
                )
            ).upper(),
            "timeframe": str(
                goal.get(
                    "timeframe",
                    "MEDIUM_TERM",
                )
            ).upper(),
            "deadline": self._optional_string(
                goal.get(
                    "deadline"
                )
            ),
            "tags": self._safe_list(
                goal.get(
                    "tags",
                    [],
                )
            ),
            "success_criteria": self._safe_list(
                goal.get(
                    "success_criteria",
                    [],
                )
            ),
            "metadata": self._safe_dict(
                goal.get(
                    "metadata",
                    {},
                )
            ),
        }

    def _normalize_context(
        self,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:

        if not isinstance(context, dict):
            return {}

        return dict(context)

    def _unique_phases(
        self,
        phases: list[SubGoalType],
    ) -> list[SubGoalType]:

        result: list[SubGoalType] = []
        seen: set[str] = set()

        for phase in phases:
            if phase.value in seen:
                continue

            seen.add(phase.value)
            result.append(phase)

        return result

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

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(value).strip()

        return normalized or None

    def _safe_int(
        self,
        value: Any,
        default: int,
    ) -> int:

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return default

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

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(value, dict):
            return dict(value)

        return {}

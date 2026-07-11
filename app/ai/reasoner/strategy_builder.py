from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class StrategyStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class StrategyPhaseType(str, Enum):
    PREPARE = "PREPARE"
    RESEARCH = "RESEARCH"
    ANALYZE = "ANALYZE"
    PLAN = "PLAN"
    PREVIEW = "PREVIEW"
    CONFIRM = "CONFIRM"
    BACKUP = "BACKUP"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    ROLLBACK = "ROLLBACK"
    REPORT = "REPORT"


@dataclass
class StrategyPhase:
    phase_id: str
    phase_type: str
    name: str
    description: str
    order: int
    required: bool
    can_skip: bool
    input_data: dict[str, Any] = field(default_factory=dict)
    expected_output: dict[str, Any] = field(default_factory=dict)
    success_conditions: list[str] = field(default_factory=list)
    failure_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionStrategy:
    strategy_id: str
    name: str
    description: str
    status: str
    goal: dict[str, Any]
    selected_option: dict[str, Any]
    risk_assessment: dict[str, Any]
    phases: list[dict[str, Any]]
    requires_research: bool
    requires_confirmation: bool
    requires_developer: bool
    allows_automatic_execution: bool
    requires_manual_review: bool
    rollback_required: bool
    validation_required: bool
    estimated_steps: int
    safety_score: float
    confidence: float
    execution_summary: list[str]
    blocking_reasons: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StrategyBuilder:

    ACCEPTABLE_DECISIONS = {
        "ACCEPT",
        "ACCEPT_WITH_CAUTION",
        "REQUIRE_RESEARCH",
        "REQUIRE_CONFIRMATION",
        "MANUAL_REVIEW",
    }

    BLOCKING_DECISIONS = {
        "REJECT",
    }

    def build(
        self,
        goal: dict[str, Any],
        options_result: dict[str, Any] | list[dict[str, Any]],
        risk_result: dict[str, Any],
        decision_graph: dict[str, Any] | None = None,
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_goal = self._normalize_goal(goal)
        options = self._extract_options(options_result)
        assessments = self._extract_assessments(risk_result)
        normalized_research = self._normalize_context(
            research_context
        )

        selected_option = self._select_option(
            options=options,
            assessments=assessments,
            risk_result=risk_result,
        )

        if selected_option is None:
            return self._build_blocked_strategy(
                goal=normalized_goal,
                reason=(
                    "Nie znaleziono dostępnej opcji "
                    "do zbudowania strategii."
                ),
                decision_graph=decision_graph,
            )

        risk_assessment = self._find_assessment(
            selected_option["option_id"],
            assessments,
        )

        if risk_assessment is None:
            return self._build_blocked_strategy(
                goal=normalized_goal,
                reason=(
                    "Nie znaleziono oceny ryzyka "
                    "dla wybranej opcji."
                ),
                decision_graph=decision_graph,
            )

        blocking_reasons = self._collect_blocking_reasons(
            selected_option,
            risk_assessment,
            normalized_research,
        )

        status = self._determine_status(
            risk_assessment=risk_assessment,
            blocking_reasons=blocking_reasons,
        )

        requires_research = bool(
            risk_assessment.get(
                "requires_research",
                False,
            )
            or selected_option.get(
                "requires_research",
                False,
            )
        )

        requires_confirmation = bool(
            risk_assessment.get(
                "requires_confirmation",
                False,
            )
            or selected_option.get(
                "requires_confirmation",
                False,
            )
        )

        requires_developer = bool(
            selected_option.get(
                "requires_developer",
                False,
            )
        )

        requires_manual_review = bool(
            risk_assessment.get(
                "requires_manual_review",
                False,
            )
        )

        validation_required = requires_developer

        rollback_required = bool(
            requires_developer
            and selected_option.get(
                "scope",
                "NONE",
            ) != "NONE"
        )

        allows_automatic_execution = self._allows_auto_execution(
            status=status,
            risk_assessment=risk_assessment,
            requires_confirmation=requires_confirmation,
            requires_manual_review=requires_manual_review,
            requires_developer=requires_developer,
        )

        phases = self._build_phases(
            goal=normalized_goal,
            selected_option=selected_option,
            risk_assessment=risk_assessment,
            requires_research=requires_research,
            requires_confirmation=requires_confirmation,
            requires_developer=requires_developer,
            requires_manual_review=requires_manual_review,
            validation_required=validation_required,
            rollback_required=rollback_required,
        )

        safety_score = self._calculate_safety_score(
            risk_assessment
        )

        confidence = self._calculate_confidence(
            goal=normalized_goal,
            selected_option=selected_option,
            risk_assessment=risk_assessment,
            research_context=normalized_research,
        )

        result = ExecutionStrategy(
            strategy_id=f"strategy_{uuid4().hex}",
            name=self._build_strategy_name(
                selected_option
            ),
            description=self._build_strategy_description(
                normalized_goal,
                selected_option,
                risk_assessment,
            ),
            status=status.value,
            goal=normalized_goal,
            selected_option=selected_option,
            risk_assessment=risk_assessment,
            phases=[
                phase.to_dict()
                for phase in phases
            ],
            requires_research=requires_research,
            requires_confirmation=requires_confirmation,
            requires_developer=requires_developer,
            allows_automatic_execution=(
                allows_automatic_execution
            ),
            requires_manual_review=(
                requires_manual_review
            ),
            rollback_required=rollback_required,
            validation_required=validation_required,
            estimated_steps=self._estimate_total_steps(
                selected_option,
                phases,
            ),
            safety_score=safety_score,
            confidence=confidence,
            execution_summary=self._build_execution_summary(
                phases
            ),
            blocking_reasons=blocking_reasons,
            metadata={
                "builder_version": "1.0.0",
                "decision_graph_id": (
                    decision_graph.get("graph_id")
                    if isinstance(
                        decision_graph,
                        dict,
                    )
                    else None
                ),
                "risk_evaluation_id": (
                    risk_result.get("evaluation_id")
                    if isinstance(
                        risk_result,
                        dict,
                    )
                    else None
                ),
                "research_available": bool(
                    normalized_research
                ),
                "selected_option_id": selected_option[
                    "option_id"
                ],
                "risk_decision": risk_assessment.get(
                    "decision",
                    "UNKNOWN",
                ),
                "risk_level": risk_assessment.get(
                    "risk_level",
                    "UNKNOWN",
                ),
            },
        )

        return result.to_dict()

    def create_strategy(
        self,
        goal: dict[str, Any],
        options_result: dict[str, Any] | list[dict[str, Any]],
        risk_result: dict[str, Any],
        decision_graph: dict[str, Any] | None = None,
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.build(
            goal=goal,
            options_result=options_result,
            risk_result=risk_result,
            decision_graph=decision_graph,
            research_context=research_context,
        )

    def generate(
        self,
        goal: dict[str, Any],
        options_result: dict[str, Any] | list[dict[str, Any]],
        risk_result: dict[str, Any],
        decision_graph: dict[str, Any] | None = None,
        research_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.build(
            goal=goal,
            options_result=options_result,
            risk_result=risk_result,
            decision_graph=decision_graph,
            research_context=research_context,
        )

    def _build_phases(
        self,
        goal: dict[str, Any],
        selected_option: dict[str, Any],
        risk_assessment: dict[str, Any],
        requires_research: bool,
        requires_confirmation: bool,
        requires_developer: bool,
        requires_manual_review: bool,
        validation_required: bool,
        rollback_required: bool,
    ) -> list[StrategyPhase]:

        phases: list[StrategyPhase] = []
        order = 1

        phases.append(
            self._make_phase(
                phase_type=StrategyPhaseType.PREPARE,
                name="Przygotowanie strategii",
                description=(
                    "Przygotowanie danych wejściowych "
                    "i sprawdzenie warunków wykonania."
                ),
                order=order,
                required=True,
                can_skip=False,
                input_data={
                    "goal": goal,
                    "selected_option_id": selected_option[
                        "option_id"
                    ],
                },
                expected_output={
                    "ready": True,
                },
                success_conditions=[
                    "Cel został poprawnie zinterpretowany.",
                    "Wybrana opcja posiada ocenę ryzyka.",
                ],
                failure_actions=[
                    "Zatrzymać proces.",
                    "Przygotować raport o brakujących danych.",
                ],
            )
        )
        order += 1

        if requires_research:
            phases.append(
                self._make_phase(
                    phase_type=StrategyPhaseType.RESEARCH,
                    name="Research",
                    description=(
                        "Uruchomienie ResearchWorkflow "
                        "i zebranie potrzebnego kontekstu."
                    ),
                    order=order,
                    required=True,
                    can_skip=False,
                    input_data={
                        "goal": goal,
                    },
                    expected_output={
                        "research_context": "dict",
                    },
                    success_conditions=[
                        "Research zakończył się poprawnie.",
                        "ResearchContext nie jest pusty.",
                    ],
                    failure_actions=[
                        "Nie wykonywać zmian w kodzie.",
                        "Przekazać proces do ręcznego przeglądu.",
                    ],
                )
            )
            order += 1

        phases.append(
            self._make_phase(
                phase_type=StrategyPhaseType.ANALYZE,
                name="Analiza rozwiązania",
                description=(
                    "Analiza wybranej opcji, zakresu "
                    "i czynników ryzyka."
                ),
                order=order,
                required=True,
                can_skip=False,
                input_data={
                    "option": selected_option,
                    "risk_assessment": risk_assessment,
                },
                expected_output={
                    "analysis_complete": True,
                },
                success_conditions=[
                    "Ryzyko zostało ocenione.",
                    "Zakres wykonania jest znany.",
                ],
                failure_actions=[
                    "Zatrzymać proces.",
                    "Wybrać inną opcję.",
                ],
            )
        )
        order += 1

        phases.append(
            self._make_phase(
                phase_type=StrategyPhaseType.PLAN,
                name="Plan wykonania",
                description=(
                    "Przygotowanie szczegółowego "
                    "planu wykonania wybranej strategii."
                ),
                order=order,
                required=True,
                can_skip=False,
                input_data={
                    "execution_plan": selected_option.get(
                        "execution_plan",
                        [],
                    ),
                },
                expected_output={
                    "execution_plan_ready": True,
                },
                success_conditions=[
                    "Plan posiada wszystkie wymagane kroki.",
                    "Każdy krok ma określony rezultat.",
                ],
                failure_actions=[
                    "Uzupełnić plan wykonania.",
                    "Nie przechodzić do realizacji.",
                ],
            )
        )
        order += 1

        if requires_developer:
            phases.append(
                self._make_phase(
                    phase_type=StrategyPhaseType.PREVIEW,
                    name="Patch Preview",
                    description=(
                        "Przygotowanie patcha "
                        "i pokazanie pełnego podglądu zmian."
                    ),
                    order=order,
                    required=True,
                    can_skip=False,
                    input_data={
                        "goal": goal,
                        "strategy": selected_option,
                    },
                    expected_output={
                        "patch_preview": "dict",
                    },
                    success_conditions=[
                        "Patch został wygenerowany.",
                        "Preview zawiera wszystkie zmieniane pliki.",
                    ],
                    failure_actions=[
                        "Nie wykonywać patcha.",
                        "Przekazać błąd do raportu.",
                    ],
                )
            )
            order += 1

        if (
            requires_confirmation
            or requires_manual_review
        ):
            phases.append(
                self._make_phase(
                    phase_type=StrategyPhaseType.CONFIRM,
                    name="Akceptacja użytkownika",
                    description=(
                        "Przekazanie strategii "
                        "i preview do zatwierdzenia."
                    ),
                    order=order,
                    required=True,
                    can_skip=False,
                    input_data={
                        "requires_manual_review": (
                            requires_manual_review
                        ),
                    },
                    expected_output={
                        "approved": True,
                    },
                    success_conditions=[
                        "Użytkownik zaakceptował wykonanie.",
                    ],
                    failure_actions=[
                        "Zatrzymać proces.",
                        "Oznaczyć strategię jako odrzuconą.",
                    ],
                )
            )
            order += 1

        if requires_developer:
            phases.append(
                self._make_phase(
                    phase_type=StrategyPhaseType.BACKUP,
                    name="Backup",
                    description=(
                        "Utworzenie kopii bezpieczeństwa "
                        "przed zmianą plików."
                    ),
                    order=order,
                    required=True,
                    can_skip=False,
                    input_data={
                        "scope": selected_option.get(
                            "scope",
                            "NONE",
                        ),
                    },
                    expected_output={
                        "backup_bundle": "dict",
                    },
                    success_conditions=[
                        "Backup został zapisany.",
                        "Rollback jest możliwy.",
                    ],
                    failure_actions=[
                        "Nie wykonywać zmian.",
                        "Zatrzymać DeveloperController.",
                    ],
                )
            )
            order += 1

            phases.append(
                self._make_phase(
                    phase_type=StrategyPhaseType.EXECUTE,
                    name="Wykonanie zmian",
                    description=(
                        "Wykonanie zatwierdzonego patcha "
                        "przez DeveloperController."
                    ),
                    order=order,
                    required=True,
                    can_skip=False,
                    input_data={
                        "selected_option": selected_option,
                    },
                    expected_output={
                        "execution_result": "dict",
                    },
                    success_conditions=[
                        "Zmiany zostały zapisane.",
                        "DeveloperController nie zgłosił błędu.",
                    ],
                    failure_actions=[
                        "Przerwać wykonanie.",
                        "Przejść do rollbacku.",
                    ],
                )
            )
            order += 1

        if validation_required:
            phases.append(
                self._make_phase(
                    phase_type=StrategyPhaseType.VALIDATE,
                    name="Walidacja",
                    description=(
                        "Sprawdzenie składni, importów "
                        "i poprawności wykonanych zmian."
                    ),
                    order=order,
                    required=True,
                    can_skip=False,
                    input_data={
                        "validator": "DeveloperValidator",
                    },
                    expected_output={
                        "validation_result": "dict",
                    },
                    success_conditions=[
                        "Walidacja składni zakończona sukcesem.",
                        "Walidacja importów zakończona sukcesem.",
                    ],
                    failure_actions=[
                        "Nie zatwierdzać wyniku.",
                        "Uruchomić rollback.",
                    ],
                )
            )
            order += 1

        if rollback_required:
            phases.append(
                self._make_phase(
                    phase_type=StrategyPhaseType.ROLLBACK,
                    name="Rollback awaryjny",
                    description=(
                        "Przywrócenie poprzednich plików "
                        "w przypadku nieudanej walidacji."
                    ),
                    order=order,
                    required=False,
                    can_skip=True,
                    input_data={
                        "rollback_manager": "RollbackManager",
                    },
                    expected_output={
                        "rollback_result": "dict",
                    },
                    success_conditions=[
                        "Poprzednia wersja została przywrócona.",
                    ],
                    failure_actions=[
                        "Zgłosić krytyczny błąd.",
                        "Zatrzymać dalsze działania.",
                    ],
                    metadata={
                        "conditional": True,
                        "run_on_validation_failure": True,
                    },
                )
            )
            order += 1

        phases.append(
            self._make_phase(
                phase_type=StrategyPhaseType.REPORT,
                name="Raport końcowy",
                description=(
                    "Przygotowanie raportu z decyzji, "
                    "wykonania, walidacji i rollbacku."
                ),
                order=order,
                required=True,
                can_skip=False,
                input_data={},
                expected_output={
                    "final_report": "dict",
                },
                success_conditions=[
                    "Raport zawiera wynik każdej fazy.",
                ],
                failure_actions=[
                    "Zwrócić raport częściowy.",
                ],
            )
        )

        return phases

    def _make_phase(
        self,
        phase_type: StrategyPhaseType,
        name: str,
        description: str,
        order: int,
        required: bool,
        can_skip: bool,
        input_data: dict[str, Any],
        expected_output: dict[str, Any],
        success_conditions: list[str],
        failure_actions: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> StrategyPhase:

        return StrategyPhase(
            phase_id=f"phase_{uuid4().hex}",
            phase_type=phase_type.value,
            name=name,
            description=description,
            order=order,
            required=required,
            can_skip=can_skip,
            input_data=input_data,
            expected_output=expected_output,
            success_conditions=success_conditions,
            failure_actions=failure_actions,
            metadata=metadata or {},
        )

    def _select_option(
        self,
        options: list[dict[str, Any]],
        assessments: list[dict[str, Any]],
        risk_result: dict[str, Any],
    ) -> dict[str, Any] | None:

        recommended_option_id = None

        if isinstance(risk_result, dict):
            recommended_option_id = risk_result.get(
                "recommended_option_id"
            )

        if recommended_option_id:
            selected = self._find_option(
                recommended_option_id,
                options,
            )

            assessment = self._find_assessment(
                recommended_option_id,
                assessments,
            )

            if (
                selected is not None
                and assessment is not None
                and assessment.get("decision")
                not in self.BLOCKING_DECISIONS
            ):
                return selected

        acceptable_options: list[
            tuple[dict[str, Any], dict[str, Any]]
        ] = []

        for option in options:
            assessment = self._find_assessment(
                option["option_id"],
                assessments,
            )

            if assessment is None:
                continue

            if assessment.get(
                "decision",
                "REJECT",
            ) not in self.ACCEPTABLE_DECISIONS:
                continue

            acceptable_options.append(
                (
                    option,
                    assessment,
                )
            )

        if not acceptable_options:
            return None

        def option_score(
            pair: tuple[
                dict[str, Any],
                dict[str, Any],
            ],
        ) -> float:

            option, assessment = pair

            confidence = self._safe_float(
                assessment.get(
                    "confidence",
                    0.0,
                ),
                0.0,
            )

            risk_score = self._safe_float(
                assessment.get(
                    "normalized_score",
                    100.0,
                ),
                100.0,
            )

            hint = self._safe_float(
                option.get(
                    "score_hint",
                    0.0,
                ),
                0.0,
            )

            return (
                confidence * 40.0
                + hint * 30.0
                - risk_score
            )

        selected_pair = max(
            acceptable_options,
            key=option_score,
        )

        return selected_pair[0]

    def _collect_blocking_reasons(
        self,
        selected_option: dict[str, Any],
        risk_assessment: dict[str, Any],
        research_context: dict[str, Any],
    ) -> list[str]:

        reasons: list[str] = []

        decision = str(
            risk_assessment.get(
                "decision",
                "REJECT",
            )
        ).upper()

        if decision == "REJECT":
            reasons.append(
                "Ocena ryzyka odrzuciła wybraną opcję."
            )

        if (
            risk_assessment.get(
                "requires_research",
                False,
            )
            and not research_context
        ):
            reasons.append(
                "Strategia wymaga ResearchContext "
                "przed automatycznym wykonaniem."
            )

        if not selected_option.get(
            "execution_plan",
            []
        ):
            reasons.append(
                "Wybrana opcja nie posiada planu wykonania."
            )

        if not selected_option.get(
            "option_id"
        ):
            reasons.append(
                "Wybrana opcja nie posiada identyfikatora."
            )

        return self._unique_strings(reasons)

    def _determine_status(
        self,
        risk_assessment: dict[str, Any],
        blocking_reasons: list[str],
    ) -> StrategyStatus:

        decision = str(
            risk_assessment.get(
                "decision",
                "REJECT",
            )
        ).upper()

        if decision == "REJECT":
            return StrategyStatus.REJECTED

        if blocking_reasons:
            return StrategyStatus.BLOCKED

        return StrategyStatus.READY

    def _allows_auto_execution(
        self,
        status: StrategyStatus,
        risk_assessment: dict[str, Any],
        requires_confirmation: bool,
        requires_manual_review: bool,
        requires_developer: bool,
    ) -> bool:

        if status != StrategyStatus.READY:
            return False

        if not requires_developer:
            return True

        if requires_confirmation:
            return False

        if requires_manual_review:
            return False

        decision = str(
            risk_assessment.get(
                "decision",
                "",
            )
        ).upper()

        return decision in {
            "ACCEPT",
            "ACCEPT_WITH_CAUTION",
        }

    def _calculate_safety_score(
        self,
        risk_assessment: dict[str, Any],
    ) -> float:

        risk_score = self._safe_float(
            risk_assessment.get(
                "normalized_score",
                100.0,
            ),
            100.0,
        )

        safety_score = (
            100.0 - risk_score
        ) / 100.0

        return round(
            max(
                0.0,
                min(
                    1.0,
                    safety_score,
                ),
            ),
            2,
        )

    def _calculate_confidence(
        self,
        goal: dict[str, Any],
        selected_option: dict[str, Any],
        risk_assessment: dict[str, Any],
        research_context: dict[str, Any],
    ) -> float:

        values = [
            self._safe_float(
                goal.get(
                    "confidence",
                    0.0,
                ),
                0.0,
            ),
            self._safe_float(
                selected_option.get(
                    "score_hint",
                    0.0,
                ),
                0.0,
            ),
            self._safe_float(
                risk_assessment.get(
                    "confidence",
                    0.0,
                ),
                0.0,
            ),
        ]

        confidence = sum(values) / len(values)

        if research_context:
            confidence += 0.05

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

    def _build_strategy_name(
        self,
        selected_option: dict[str, Any],
    ) -> str:

        option_name = str(
            selected_option.get(
                "name",
                "Strategia wykonania",
            )
        ).strip()

        return f"Strategia: {option_name}"

    def _build_strategy_description(
        self,
        goal: dict[str, Any],
        selected_option: dict[str, Any],
        risk_assessment: dict[str, Any],
    ) -> str:

        return (
            f"Realizacja celu typu {goal['goal_type']} "
            f"przez strategię "
            f"{selected_option['strategy_type']}. "
            f"Poziom ryzyka: "
            f"{risk_assessment.get('risk_level', 'UNKNOWN')}."
        )

    def _estimate_total_steps(
        self,
        selected_option: dict[str, Any],
        phases: list[StrategyPhase],
    ) -> int:

        option_steps = self._safe_int(
            selected_option.get(
                "estimated_steps",
                0,
            ),
            0,
        )

        return max(
            option_steps,
            len(phases),
        )

    def _build_execution_summary(
        self,
        phases: list[StrategyPhase],
    ) -> list[str]:

        return [
            (
                f"{phase.order}. "
                f"{phase.name} "
                f"({phase.phase_type})"
            )
            for phase in phases
        ]

    def _build_blocked_strategy(
        self,
        goal: dict[str, Any],
        reason: str,
        decision_graph: dict[str, Any] | None,
    ) -> dict[str, Any]:

        result = ExecutionStrategy(
            strategy_id=f"strategy_{uuid4().hex}",
            name="Strategia zablokowana",
            description=reason,
            status=StrategyStatus.BLOCKED.value,
            goal=goal,
            selected_option={},
            risk_assessment={},
            phases=[],
            requires_research=False,
            requires_confirmation=False,
            requires_developer=False,
            allows_automatic_execution=False,
            requires_manual_review=True,
            rollback_required=False,
            validation_required=False,
            estimated_steps=0,
            safety_score=0.0,
            confidence=0.0,
            execution_summary=[],
            blocking_reasons=[
                reason
            ],
            metadata={
                "builder_version": "1.0.0",
                "decision_graph_id": (
                    decision_graph.get("graph_id")
                    if isinstance(
                        decision_graph,
                        dict,
                    )
                    else None
                ),
            },
        )

        return result.to_dict()

    def _extract_options(
        self,
        options_result: dict[str, Any] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        if isinstance(options_result, list):
            raw_options = options_result
        elif isinstance(options_result, dict):
            raw_options = options_result.get(
                "options",
                [],
            )
        else:
            raise TypeError(
                "StrategyBuilder wymaga listy opcji "
                "lub wyniku OptionGenerator."
            )

        if not isinstance(raw_options, list):
            raise TypeError(
                "Pole options musi być listą."
            )

        return [
            self._normalize_option(option)
            for option in raw_options
            if isinstance(option, dict)
        ]

    def _extract_assessments(
        self,
        risk_result: dict[str, Any],
    ) -> list[dict[str, Any]]:

        if not isinstance(risk_result, dict):
            raise TypeError(
                "StrategyBuilder wymaga wyniku RiskEvaluator."
            )

        assessments = risk_result.get(
            "assessments",
            [],
        )

        if not isinstance(assessments, list):
            return []

        return [
            dict(assessment)
            for assessment in assessments
            if isinstance(assessment, dict)
        ]

    def _find_option(
        self,
        option_id: str,
        options: list[dict[str, Any]],
    ) -> dict[str, Any] | None:

        for option in options:
            if option.get("option_id") == option_id:
                return option

        return None

    def _find_assessment(
        self,
        option_id: str,
        assessments: list[dict[str, Any]],
    ) -> dict[str, Any] | None:

        for assessment in assessments:
            if assessment.get("option_id") == option_id:
                return assessment

        return None

    def _normalize_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(goal, dict):
            raise TypeError(
                "StrategyBuilder wymaga celu typu dict."
            )

        return {
            "original_request": str(
                goal.get(
                    "original_request",
                    "",
                )
            ),
            "goal": str(
                goal.get(
                    "goal",
                    "",
                )
            ),
            "goal_type": str(
                goal.get(
                    "goal_type",
                    "UNKNOWN",
                )
            ).upper(),
            "priority": str(
                goal.get(
                    "priority",
                    "LOW",
                )
            ).upper(),
            "complexity": str(
                goal.get(
                    "complexity",
                    "LOW",
                )
            ).upper(),
            "requires_research": bool(
                goal.get(
                    "requires_research",
                    False,
                )
            ),
            "requires_developer": bool(
                goal.get(
                    "requires_developer",
                    False,
                )
            ),
            "requires_confirmation": bool(
                goal.get(
                    "requires_confirmation",
                    False,
                )
            ),
            "confidence": max(
                0.0,
                min(
                    1.0,
                    self._safe_float(
                        goal.get(
                            "confidence",
                            0.0,
                        ),
                        0.0,
                    ),
                ),
            ),
            "keywords": self._safe_list(
                goal.get(
                    "keywords",
                    [],
                )
            ),
            "detected_modules": self._safe_list(
                goal.get(
                    "detected_modules",
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

    def _normalize_option(
        self,
        option: dict[str, Any],
    ) -> dict[str, Any]:

        option_id = str(
            option.get(
                "option_id",
                "",
            )
        ).strip()

        if not option_id:
            option_id = f"option_{uuid4().hex}"

        return {
            "option_id": option_id,
            "name": str(
                option.get(
                    "name",
                    "Nieznana opcja",
                )
            ),
            "description": str(
                option.get(
                    "description",
                    "",
                )
            ),
            "strategy_type": str(
                option.get(
                    "strategy_type",
                    "MANUAL_REVIEW",
                )
            ).upper(),
            "scope": str(
                option.get(
                    "scope",
                    "NONE",
                )
            ).upper(),
            "effort": str(
                option.get(
                    "effort",
                    "LOW",
                )
            ).upper(),
            "requires_research": bool(
                option.get(
                    "requires_research",
                    False,
                )
            ),
            "requires_developer": bool(
                option.get(
                    "requires_developer",
                    False,
                )
            ),
            "requires_confirmation": bool(
                option.get(
                    "requires_confirmation",
                    False,
                )
            ),
            "estimated_steps": max(
                0,
                self._safe_int(
                    option.get(
                        "estimated_steps",
                        0,
                    ),
                    0,
                ),
            ),
            "expected_benefits": self._safe_list(
                option.get(
                    "expected_benefits",
                    [],
                )
            ),
            "expected_drawbacks": self._safe_list(
                option.get(
                    "expected_drawbacks",
                    [],
                )
            ),
            "assumptions": self._safe_list(
                option.get(
                    "assumptions",
                    [],
                )
            ),
            "execution_plan": self._safe_list(
                option.get(
                    "execution_plan",
                    [],
                )
            ),
            "score_hint": max(
                0.0,
                min(
                    1.0,
                    self._safe_float(
                        option.get(
                            "score_hint",
                            0.0,
                        ),
                        0.0,
                    ),
                ),
            ),
            "metadata": self._safe_dict(
                option.get(
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
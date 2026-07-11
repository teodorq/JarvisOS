from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class ImprovementBrainStatus(str, Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    DECIDING = "DECIDING"
    PLANNING = "PLANNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    EXECUTING = "EXECUTING"
    LEARNING = "LEARNING"
    COMPLETED = "COMPLETED"
    NO_ACTION = "NO_ACTION"
    FAILED = "FAILED"


class ImprovementBrainDecision(str, Enum):
    START_EVOLUTION = "START_EVOLUTION"
    START_CONTINUOUS_DEV = "START_CONTINUOUS_DEV"
    RUN_RESEARCH = "RUN_RESEARCH"
    RUN_REASONER = "RUN_REASONER"
    WAIT_FOR_APPROVAL = "WAIT_FOR_APPROVAL"
    NO_ACTION = "NO_ACTION"
    STOP = "STOP"


@dataclass
class ImprovementProposal:
    proposal_id: str
    title: str
    description: str
    category: str
    priority: str
    score: float
    confidence: float
    risks: list[str]
    benefits: list[str]
    affected_files: list[str]
    affected_modules: list[str]
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImprovementBrainResult:
    session_id: str
    status: str
    decision: str
    selected_proposal: dict[str, Any]
    proposals: list[dict[str, Any]]
    research: dict[str, Any]
    reasoning: dict[str, Any]
    execution: dict[str, Any]
    lessons: list[str]
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImprovementBrain:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        research_service: Any | None = None,
        reasoning_service: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
        ).strip()

        if not self.project_root:
            raise ValueError(
                "ImprovementBrain wymaga project_root."
            )

        self.research_service = research_service
        self.reasoning_service = reasoning_service
        self.evolution_controller = evolution_controller
        self.continuous_dev_controller = (
            continuous_dev_controller
        )

        self._sessions: dict[
            str,
            dict[str, Any],
        ] = {}

    def analyze(
        self,
        objective: str,
        project_context: dict[str, Any] | None = None,
        auto_execute: bool = False,
        approved: bool | None = None,
        mode: str = "SAFE_AUTONOMOUS",
    ) -> dict[str, Any]:

        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            return {
                "success": False,
                "status": ImprovementBrainStatus.FAILED.value,
                "error": (
                    "ImprovementBrain wymaga celu analizy."
                ),
            }

        session_id = (
            f"improvement_brain_{uuid4().hex}"
        )

        context = self._safe_dict(
            project_context
        )

        state = {
            "session_id": session_id,
            "objective": normalized_objective,
            "status": ImprovementBrainStatus.ANALYZING.value,
            "decision": ImprovementBrainDecision.NO_ACTION.value,
            "proposals": [],
            "selected_proposal": {},
            "research": {},
            "reasoning": {},
            "execution": {},
            "lessons": [],
            "errors": [],
            "warnings": [],
            "mode": str(mode).upper(),
        }

        self._sessions[
            session_id
        ] = state

        try:
            proposals = self._generate_proposals(
                objective=normalized_objective,
                context=context,
            )

            state["proposals"] = proposals

            if not proposals:
                state["status"] = (
                    ImprovementBrainStatus.NO_ACTION.value
                )
                state["decision"] = (
                    ImprovementBrainDecision.NO_ACTION.value
                )

                return self._result(
                    state=state,
                    success=True,
                )

            selected = self._select_best(
                proposals
            )

            state["selected_proposal"] = selected
            state["status"] = (
                ImprovementBrainStatus.DECIDING.value
            )

            research = self._run_research(
                objective=normalized_objective,
                proposal=selected,
                context=context,
            )

            state["research"] = research

            reasoning = self._run_reasoning(
                objective=normalized_objective,
                proposal=selected,
                research=research,
                context=context,
            )

            state["reasoning"] = reasoning

            decision = self._choose_decision(
                proposal=selected,
                reasoning=reasoning,
                auto_execute=auto_execute,
            )

            state["decision"] = decision

            if decision == (
                ImprovementBrainDecision
                .WAIT_FOR_APPROVAL
                .value
            ):
                state["status"] = (
                    ImprovementBrainStatus
                    .WAITING_FOR_APPROVAL
                    .value
                )

                if approved is True:
                    return self.execute(
                        session_id=session_id,
                        approved=True,
                        context=context,
                    )

                return self._result(
                    state=state,
                    success=True,
                )

            if decision == (
                ImprovementBrainDecision.NO_ACTION.value
            ):
                state["status"] = (
                    ImprovementBrainStatus.NO_ACTION.value
                )

                return self._result(
                    state=state,
                    success=True,
                )

            if auto_execute:
                return self.execute(
                    session_id=session_id,
                    approved=approved,
                    context=context,
                )

            state["status"] = (
                ImprovementBrainStatus.PLANNING.value
            )

            return self._result(
                state=state,
                success=True,
            )

        except Exception as error:
            message = (
                f"ImprovementBrain error: "
                f"{type(error).__name__}: {error}"
            )

            state["status"] = (
                ImprovementBrainStatus.FAILED.value
            )

            state["errors"] = self._unique_strings(
                state["errors"] + [message]
            )

            return self._result(
                state=state,
                success=False,
            )

    def execute(
        self,
        session_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._sessions.get(
            str(session_id).strip()
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "session_id": session_id,
                "error": (
                    "Nie znaleziono sesji "
                    "ImprovementBrain."
                ),
            }

        decision = str(
            state.get(
                "decision",
                ImprovementBrainDecision.NO_ACTION.value,
            )
        ).upper()

        selected = self._safe_dict(
            state.get(
                "selected_proposal",
                {},
            )
        )

        normalized_context = self._safe_dict(
            context
        )

        if (
            decision
            == ImprovementBrainDecision.WAIT_FOR_APPROVAL.value
            and approved is not True
        ):
            state["status"] = (
                ImprovementBrainStatus
                .WAITING_FOR_APPROVAL
                .value
            )

            return self._result(
                state=state,
                success=True,
            )

        state["status"] = (
            ImprovementBrainStatus.EXECUTING.value
        )

        try:
            if decision == (
                ImprovementBrainDecision
                .START_EVOLUTION
                .value
            ):
                execution = self._start_evolution(
                    proposal=selected,
                    context=normalized_context,
                    approved=approved,
                    mode=str(
                        state.get(
                            "mode",
                            "SAFE_AUTONOMOUS",
                        )
                    ),
                )

            elif decision == (
                ImprovementBrainDecision
                .START_CONTINUOUS_DEV
                .value
            ):
                execution = (
                    self._start_continuous_dev(
                        proposal=selected,
                        context=normalized_context,
                        approved=approved,
                    )
                )

            elif decision == (
                ImprovementBrainDecision
                .RUN_RESEARCH
                .value
            ):
                execution = self._run_research(
                    objective=str(
                        state.get(
                            "objective",
                            "",
                        )
                    ),
                    proposal=selected,
                    context=normalized_context,
                )

            elif decision == (
                ImprovementBrainDecision
                .RUN_REASONER
                .value
            ):
                execution = self._run_reasoning(
                    objective=str(
                        state.get(
                            "objective",
                            "",
                        )
                    ),
                    proposal=selected,
                    research=self._safe_dict(
                        state.get(
                            "research",
                            {},
                        )
                    ),
                    context=normalized_context,
                )

            else:
                execution = {
                    "success": True,
                    "status": "NO_ACTION",
                }

            state["execution"] = (
                self._normalize_result(
                    execution
                )
            )

            if self._detect_success(
                state["execution"]
            ):
                state["status"] = (
                    ImprovementBrainStatus
                    .LEARNING
                    .value
                )

                self._learn_from_result(
                    state
                )

                state["status"] = (
                    ImprovementBrainStatus
                    .COMPLETED
                    .value
                )

                return self._result(
                    state=state,
                    success=True,
                )

            error = self._extract_error(
                state["execution"]
            )

            state["errors"] = self._unique_strings(
                state["errors"] + [error]
            )

            state["status"] = (
                ImprovementBrainStatus.FAILED.value
            )

            return self._result(
                state=state,
                success=False,
            )

        except Exception as error:
            message = (
                f"ImprovementBrain execute error: "
                f"{type(error).__name__}: {error}"
            )

            state["errors"] = self._unique_strings(
                state["errors"] + [message]
            )

            state["status"] = (
                ImprovementBrainStatus.FAILED.value
            )

            return self._result(
                state=state,
                success=False,
            )

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        state = self._sessions.get(
            str(session_id).strip()
        )

        if state is None:
            return None

        return dict(
            state
        )

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        sessions = list(
            self._sessions.values()
        )

        return [
            dict(item)
            for item in sessions[
                -max(
                    1,
                    int(limit),
                ):
            ]
        ]

    def _generate_proposals(
        self,
        objective: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:

        raw_items: list[Any] = []

        for key in (
            "problems",
            "issues",
            "warnings",
            "suggestions",
            "improvements",
            "recommendations",
        ):
            raw_items.extend(
                self._safe_list(
                    context.get(
                        key,
                        [],
                    )
                )
            )

        proposals: list[
            ImprovementProposal
        ] = []

        for index, item in enumerate(
            raw_items,
            start=1,
        ):
            normalized = self._normalize_item(
                item
            )

            proposal = ImprovementProposal(
                proposal_id=f"improvement_proposal_{uuid4().hex}",
                title=normalized.get(
                    "title",
                    f"Ulepszenie {index}",
                ),
                description=normalized.get(
                    "description",
                    "",
                ),
                category=self._detect_category(
                    normalized
                ),
                priority=self._detect_priority(
                    normalized
                ),
                score=self._calculate_score(
                    normalized
                ),
                confidence=self._calculate_confidence(
                    normalized
                ),
                risks=self._safe_string_list(
                    normalized.get(
                        "risks",
                        [],
                    )
                ),
                benefits=self._safe_string_list(
                    normalized.get(
                        "benefits",
                        [],
                    )
                ),
                affected_files=self._safe_string_list(
                    normalized.get(
                        "affected_files",
                        normalized.get(
                            "files",
                            [],
                        ),
                    )
                ),
                affected_modules=self._safe_string_list(
                    normalized.get(
                        "affected_modules",
                        normalized.get(
                            "modules",
                            [],
                        ),
                    )
                ),
                source=str(
                    normalized.get(
                        "source",
                        "project_context",
                    )
                ),
                metadata={
                    "objective": objective,
                    "raw_item": normalized,
                },
            )

            proposals.append(
                proposal
            )

        if not proposals:
            proposals.append(
                ImprovementProposal(
                    proposal_id=(
                        f"improvement_proposal_"
                        f"{uuid4().hex}"
                    ),
                    title=objective[
                        :120
                    ],
                    description=objective,
                    category="GENERAL",
                    priority="MEDIUM",
                    score=50.0,
                    confidence=0.55,
                    risks=[
                        "Zakres wymaga dalszej analizy."
                    ],
                    benefits=[
                        "Potencjalna poprawa projektu."
                    ],
                    affected_files=[],
                    affected_modules=[],
                    source="objective",
                    metadata={
                        "objective": objective,
                    },
                )
            )

        proposals.sort(
            key=lambda item: (
                -item.score,
                -item.confidence,
            )
        )

        return [
            proposal.to_dict()
            for proposal in proposals
        ]

    def _select_best(
        self,
        proposals: list[dict[str, Any]],
    ) -> dict[str, Any]:

        valid = [
            dict(item)
            for item in proposals
            if isinstance(
                item,
                dict,
            )
        ]

        valid.sort(
            key=lambda item: (
                -self._safe_float(
                    item.get(
                        "score",
                        0.0,
                    ),
                    0.0,
                ),
                -self._safe_float(
                    item.get(
                        "confidence",
                        0.0,
                    ),
                    0.0,
                ),
            )
        )

        return valid[0]

    def _choose_decision(
        self,
        proposal: dict[str, Any],
        reasoning: dict[str, Any],
        auto_execute: bool,
    ) -> str:

        priority = str(
            proposal.get(
                "priority",
                "MEDIUM",
            )
        ).upper()

        category = str(
            proposal.get(
                "category",
                "GENERAL",
            )
        ).upper()

        requires_confirmation = bool(
            reasoning.get(
                "requires_confirmation",
                False,
            )
        )

        if (
            priority in {
                "HIGH",
                "CRITICAL",
            }
            or category
            in {
                "SECURITY",
                "ARCHITECTURE",
            }
            or requires_confirmation
        ):
            return (
                ImprovementBrainDecision
                .WAIT_FOR_APPROVAL
                .value
            )

        if auto_execute:
            return (
                ImprovementBrainDecision
                .START_EVOLUTION
                .value
            )

        return (
            ImprovementBrainDecision
            .START_CONTINUOUS_DEV
            .value
        )

    def _run_research(
        self,
        objective: str,
        proposal: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        service = self.research_service

        if service is None:
            return {
                "success": True,
                "status": "SKIPPED",
                "message": (
                    "ResearchService nie został podłączony."
                ),
            }

        command = (
            f"Przeanalizuj projekt pod kątem: "
            f"{proposal.get('title', objective)}. "
            f"{proposal.get('description', '')}"
        )

        if hasattr(
            service,
            "execute",
        ):
            result = service.execute(
                command
            )

        elif hasattr(
            service,
            "run",
        ):
            result = service.run(
                command
            )

        elif hasattr(
            service,
            "research",
        ):
            result = service.research(
                command
            )

        elif callable(
            service
        ):
            result = service(
                command
            )

        else:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ResearchService nie posiada "
                    "obsługiwanej metody."
                ),
            }

        return self._normalize_result(
            result
        )

    def _run_reasoning(
        self,
        objective: str,
        proposal: dict[str, Any],
        research: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        service = self.reasoning_service

        if service is None:
            return {
                "success": True,
                "status": "SKIPPED",
                "requires_confirmation": False,
            }

        request = (
            f"Podejmij decyzję dotyczącą ulepszenia: "
            f"{proposal.get('title', objective)}. "
            f"{proposal.get('description', '')}"
        )

        if hasattr(
            service,
            "reason",
        ):
            result = service.reason(
                user_request=request,
                research_context=research,
                project_context=context,
                auto_execute=False,
            )

        elif hasattr(
            service,
            "analyze",
        ):
            result = service.analyze(
                user_request=request,
                research_context=research,
                project_context=context,
            )

        elif hasattr(
            service,
            "handle",
        ):
            result = service.handle(
                command=request,
                context={
                    "project_context": context,
                    "research_context": research,
                },
            )

        elif callable(
            service
        ):
            result = service(
                request
            )

        else:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ReasoningService nie posiada "
                    "obsługiwanej metody."
                ),
            }

        return self._normalize_result(
            result
        )

    def _start_evolution(
        self,
        proposal: dict[str, Any],
        context: dict[str, Any],
        approved: bool | None,
        mode: str,
    ) -> dict[str, Any]:

        controller = self.evolution_controller

        if controller is None:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "EvolutionController nie został "
                    "podłączony."
                ),
            }

        objective = self._proposal_objective(
            proposal
        )

        effective_mode = str(
            mode
        ).upper()

        if approved is True:
            effective_mode = "AUTONOMOUS"

        return self._normalize_result(
            controller.create_and_start(
                objective=objective,
                mode=effective_mode,
                context=context,
                metadata={
                    "source": "ImprovementBrain",
                    "proposal_id": proposal.get(
                        "proposal_id"
                    ),
                },
            )
        )

    def _start_continuous_dev(
        self,
        proposal: dict[str, Any],
        context: dict[str, Any],
        approved: bool | None,
    ) -> dict[str, Any]:

        controller = self.continuous_dev_controller

        if controller is None:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ContinuousDevController nie został "
                    "podłączony."
                ),
            }

        return self._normalize_result(
            controller.create_and_start(
                objective=self._proposal_objective(
                    proposal
                ),
                auto_approve=(
                    approved is True
                ),
                context=context,
                metadata={
                    "source": "ImprovementBrain",
                    "proposal_id": proposal.get(
                        "proposal_id"
                    ),
                },
            )
        )

    def _learn_from_result(
        self,
        state: dict[str, Any],
    ) -> None:

        execution = self._safe_dict(
            state.get(
                "execution",
                {},
            )
        )

        lessons: list[Any] = []

        lessons.extend(
            self._safe_list(
                execution.get(
                    "lessons",
                    [],
                )
            )
        )

        summary = execution.get(
            "summary"
        )

        if isinstance(
            summary,
            dict,
        ):
            lessons.extend(
                self._safe_list(
                    summary.get(
                        "lessons",
                        [],
                    )
                )
            )

        if not lessons:
            lessons.append(
                (
                    "Sesja ImprovementBrain została "
                    "zakończona i zapisana do historii."
                )
            )

        state["lessons"] = self._unique_strings(
            state.get(
                "lessons",
                [],
            )
            + lessons
        )

    def _result(
        self,
        state: dict[str, Any],
        success: bool,
    ) -> dict[str, Any]:

        result = ImprovementBrainResult(
            session_id=str(
                state.get(
                    "session_id",
                    "",
                )
            ),
            status=str(
                state.get(
                    "status",
                    "UNKNOWN",
                )
            ),
            decision=str(
                state.get(
                    "decision",
                    ImprovementBrainDecision.NO_ACTION.value,
                )
            ),
            selected_proposal=self._safe_dict(
                state.get(
                    "selected_proposal",
                    {},
                )
            ),
            proposals=[
                dict(item)
                for item in self._safe_list(
                    state.get(
                        "proposals",
                        [],
                    )
                )
                if isinstance(
                    item,
                    dict,
                )
            ],
            research=self._safe_dict(
                state.get(
                    "research",
                    {},
                )
            ),
            reasoning=self._safe_dict(
                state.get(
                    "reasoning",
                    {},
                )
            ),
            execution=self._safe_dict(
                state.get(
                    "execution",
                    {},
                )
            ),
            lessons=self._safe_string_list(
                state.get(
                    "lessons",
                    [],
                )
            ),
            errors=self._safe_string_list(
                state.get(
                    "errors",
                    [],
                )
            ),
            warnings=self._safe_string_list(
                state.get(
                    "warnings",
                    [],
                )
            ),
            metadata={
                "brain_version": "1.0.0",
                "project_root": self.project_root,
                "objective": state.get(
                    "objective"
                ),
                "mode": state.get(
                    "mode"
                ),
                "success": bool(
                    success
                ),
            },
        )

        response = result.to_dict()
        response["success"] = bool(
            success
        )

        return response

    def _proposal_objective(
        self,
        proposal: dict[str, Any],
    ) -> str:

        title = str(
            proposal.get(
                "title",
                "",
            )
        ).strip()

        description = str(
            proposal.get(
                "description",
                "",
            )
        ).strip()

        return (
            f"{title}. {description}"
        ).strip(
            ". "
        )

    def _normalize_item(
        self,
        item: Any,
    ) -> dict[str, Any]:

        if isinstance(
            item,
            dict,
        ):
            result = dict(
                item
            )

            result.setdefault(
                "title",
                str(
                    result.get(
                        "name",
                        result.get(
                            "message",
                            "Wykryte ulepszenie",
                        ),
                    )
                ),
            )

            result.setdefault(
                "description",
                str(
                    result.get(
                        "details",
                        result.get(
                            "message",
                            result.get(
                                "title",
                                "",
                            ),
                        ),
                    )
                ),
            )

            return result

        text = str(
            item
        ).strip()

        return {
            "title": text[:120],
            "description": text,
        }

    def _detect_category(
        self,
        item: dict[str, Any],
    ) -> str:

        explicit = item.get(
            "category",
            item.get(
                "type",
                item.get(
                    "improvement_type"
                ),
            ),
        )

        if explicit:
            return str(
                explicit
            ).upper()

        text = (
            f"{item.get('title', '')} "
            f"{item.get('description', '')}"
        ).lower()

        rules = {
            "SECURITY": (
                "security",
                "bezpieczeń",
                "podatność",
                "vulnerability",
            ),
            "BUG_FIX": (
                "bug",
                "błąd",
                "blad",
                "exception",
                "traceback",
                "awaria",
            ),
            "PERFORMANCE": (
                "wydajność",
                "wydajnosc",
                "performance",
                "slow",
                "wolno",
            ),
            "TESTING": (
                "test",
                "coverage",
                "regression",
            ),
            "ARCHITECTURE": (
                "architektura",
                "architecture",
                "dependency",
                "zależność",
                "zaleznosc",
            ),
            "REFACTOR": (
                "refactor",
                "duplikacja",
                "cleanup",
                "czytelność",
                "czytelnosc",
            ),
        }

        for category, keywords in rules.items():
            if any(
                keyword in text
                for keyword in keywords
            ):
                return category

        return "GENERAL"

    def _detect_priority(
        self,
        item: dict[str, Any],
    ) -> str:

        explicit = item.get(
            "priority",
            item.get(
                "severity",
            ),
        )

        if explicit:
            normalized = str(
                explicit
            ).upper()

            if normalized in {
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
            }:
                return normalized

        text = (
            f"{item.get('title', '')} "
            f"{item.get('description', '')}"
        ).lower()

        if any(
            keyword in text
            for keyword in (
                "critical",
                "krytyczny",
                "utrata danych",
                "data loss",
            )
        ):
            return "CRITICAL"

        if any(
            keyword in text
            for keyword in (
                "high",
                "wysoki",
                "awaria",
                "crash",
                "exception",
            )
        ):
            return "HIGH"

        if any(
            keyword in text
            for keyword in (
                "low",
                "niski",
                "kosmetyczny",
            )
        ):
            return "LOW"

        return "MEDIUM"

    def _calculate_score(
        self,
        item: dict[str, Any],
    ) -> float:

        priority = self._detect_priority(
            item
        )

        base = {
            "LOW": 25.0,
            "MEDIUM": 50.0,
            "HIGH": 75.0,
            "CRITICAL": 95.0,
        }.get(
            priority,
            50.0,
        )

        affected_files = self._safe_list(
            item.get(
                "affected_files",
                item.get(
                    "files",
                    [],
                ),
            )
        )

        affected_modules = self._safe_list(
            item.get(
                "affected_modules",
                item.get(
                    "modules",
                    [],
                ),
            )
        )

        base += min(
            5.0,
            len(
                affected_files
            ),
        )

        base += min(
            5.0,
            len(
                affected_modules
            ) * 1.5,
        )

        return round(
            min(
                100.0,
                base,
            ),
            2,
        )

    def _calculate_confidence(
        self,
        item: dict[str, Any],
    ) -> float:

        confidence = 0.50

        if item.get(
            "description"
        ):
            confidence += 0.15

        if item.get(
            "severity"
        ) or item.get(
            "priority"
        ):
            confidence += 0.10

        if item.get(
            "affected_files"
        ) or item.get(
            "files"
        ):
            confidence += 0.10

        if item.get(
            "evidence"
        ):
            confidence += 0.10

        return round(
            min(
                1.0,
                confidence,
            ),
            2,
        )

    def _normalize_result(
        self,
        result: Any,
    ) -> dict[str, Any]:

        if isinstance(
            result,
            dict,
        ):
            return dict(
                result
            )

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _detect_success(
        self,
        result: dict[str, Any],
    ) -> bool:

        value = result.get(
            "success"
        )

        if isinstance(
            value,
            bool,
        ):
            return value

        status = str(
            result.get(
                "status",
                "",
            )
        ).upper()

        return status in {
            "SUCCESS",
            "COMPLETED",
            "DONE",
            "LEARNING",
            "WAITING_FOR_APPROVAL",
            "SKIPPED",
            "NO_ACTION",
            "NO_CHANGES",
        }

    def _extract_error(
        self,
        result: dict[str, Any],
    ) -> str:

        for key in (
            "error",
            "message",
            "details",
        ):
            value = result.get(
                key
            )

            if value:
                return str(
                    value
                )

        return (
            "ImprovementBrain otrzymał "
            "nieudany wynik."
        )

    def _safe_float(
        self,
        value: Any,
        default: float,
    ) -> float:

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(
            value,
            list,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            tuple,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            set,
        ):
            return list(
                value
            )

        if value is None:
            return []

        return [
            value
        ]

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        return self._unique_strings(
            self._safe_list(
                value
            )
        )

    def _unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            text = str(
                value
            ).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                text
            )

        return result

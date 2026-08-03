"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class DevelopmentCycleStatus(str, Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    RESEARCHING = "RESEARCHING"
    REASONING = "REASONING"
    PREPARING_PATCH = "PREPARING_PATCH"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    ROLLING_BACK = "ROLLING_BACK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DevelopmentCycleStage(str, Enum):
    ANALYZE = "ANALYZE"
    DETECT_IMPROVEMENT = "DETECT_IMPROVEMENT"
    PLAN = "PLAN"
    RESEARCH = "RESEARCH"
    REASON = "REASON"
    PREPARE_PATCH = "PREPARE_PATCH"
    APPROVE = "APPROVE"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    ROLLBACK = "ROLLBACK"
    REPORT = "REPORT"


class DevelopmentCycleResult(str, Enum):
    UNKNOWN = "UNKNOWN"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    NO_CHANGES = "NO_CHANGES"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


@dataclass
class CycleEvent:
    event_id: str
    event_type: str
    message: str
    timestamp: str
    stage: str | None = None
    progress: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DevelopmentCycleData:
    cycle_id: str
    project_root: str
    objective: str
    status: str
    current_stage: str | None
    result: str
    progress: float
    iteration: int
    max_iterations: int
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None
    analysis: dict[str, Any]
    detected_improvements: list[dict[str, Any]]
    selected_improvement: dict[str, Any]
    plan: dict[str, Any]
    research: dict[str, Any]
    reasoning: dict[str, Any]
    patch: dict[str, Any]
    approval: dict[str, Any]
    execution: dict[str, Any]
    validation: dict[str, Any]
    rollback: dict[str, Any]
    report: dict[str, Any]
    events: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]
    lessons: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DevelopmentCycle:

    STAGE_PROGRESS = {
        DevelopmentCycleStage.ANALYZE.value: 0.10,
        DevelopmentCycleStage.DETECT_IMPROVEMENT.value: 0.20,
        DevelopmentCycleStage.PLAN.value: 0.30,
        DevelopmentCycleStage.RESEARCH.value: 0.40,
        DevelopmentCycleStage.REASON.value: 0.50,
        DevelopmentCycleStage.PREPARE_PATCH.value: 0.62,
        DevelopmentCycleStage.APPROVE.value: 0.68,
        DevelopmentCycleStage.EXECUTE.value: 0.78,
        DevelopmentCycleStage.VALIDATE.value: 0.90,
        DevelopmentCycleStage.ROLLBACK.value: 0.94,
        DevelopmentCycleStage.REPORT.value: 0.98,
    }

    STAGE_STATUS = {
        DevelopmentCycleStage.ANALYZE.value: (
            DevelopmentCycleStatus.ANALYZING.value
        ),
        DevelopmentCycleStage.DETECT_IMPROVEMENT.value: (
            DevelopmentCycleStatus.ANALYZING.value
        ),
        DevelopmentCycleStage.PLAN.value: (
            DevelopmentCycleStatus.PLANNING.value
        ),
        DevelopmentCycleStage.RESEARCH.value: (
            DevelopmentCycleStatus.RESEARCHING.value
        ),
        DevelopmentCycleStage.REASON.value: (
            DevelopmentCycleStatus.REASONING.value
        ),
        DevelopmentCycleStage.PREPARE_PATCH.value: (
            DevelopmentCycleStatus.PREPARING_PATCH.value
        ),
        DevelopmentCycleStage.APPROVE.value: (
            DevelopmentCycleStatus.WAITING_FOR_APPROVAL.value
        ),
        DevelopmentCycleStage.EXECUTE.value: (
            DevelopmentCycleStatus.EXECUTING.value
        ),
        DevelopmentCycleStage.VALIDATE.value: (
            DevelopmentCycleStatus.VALIDATING.value
        ),
        DevelopmentCycleStage.ROLLBACK.value: (
            DevelopmentCycleStatus.ROLLING_BACK.value
        ),
        DevelopmentCycleStage.REPORT.value: (
            DevelopmentCycleStatus.COMPLETED.value
        ),
    }

    def __init__(
        self,
        project_root: str,
        objective: str,
        max_iterations: int = 10,
        cycle_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        now = self._utc_now()

        self.cycle_id = (
            str(cycle_id).strip()
            if cycle_id
            else f"development_cycle_{uuid4().hex}"
        )

        self.project_root = str(project_root).strip()
        self.objective = str(objective).strip()

        if not self.project_root:
            raise ValueError(
                "DevelopmentCycle wymaga project_root."
            )

        if not self.objective:
            raise ValueError(
                "DevelopmentCycle wymaga celu cyklu."
            )

        self.status = DevelopmentCycleStatus.CREATED.value
        self.current_stage: str | None = None
        self.result = DevelopmentCycleResult.UNKNOWN.value
        self.progress = 0.0

        self.iteration = 0
        self.max_iterations = max(
            1,
            int(max_iterations),
        )

        self.created_at = now
        self.updated_at = now
        self.started_at: str | None = None
        self.completed_at: str | None = None

        self.analysis: dict[str, Any] = {}
        self.detected_improvements: list[
            dict[str, Any]
        ] = []
        self.selected_improvement: dict[str, Any] = {}
        self.plan: dict[str, Any] = {}
        self.research: dict[str, Any] = {}
        self.reasoning: dict[str, Any] = {}
        self.patch: dict[str, Any] = {}
        self.approval: dict[str, Any] = {}
        self.execution: dict[str, Any] = {}
        self.validation: dict[str, Any] = {}
        self.rollback: dict[str, Any] = {}
        self.report: dict[str, Any] = {}

        self.events: list[CycleEvent] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.lessons: list[str] = []

        self.metadata: dict[str, Any] = {
            "cycle_version": "1.0.0",
            **(metadata or {}),
        }

        self._add_event(
            event_type="CREATED",
            message="Utworzono nowy cykl rozwoju.",
            progress=0.0,
        )

    def start(
        self,
    ) -> dict[str, Any]:

        self.started_at = (
            self.started_at
            or self._utc_now()
        )

        self.status = (
            DevelopmentCycleStatus.ANALYZING.value
        )

        self.set_stage(
            DevelopmentCycleStage.ANALYZE.value
        )

        self._add_event(
            event_type="STARTED",
            message="Rozpoczęto cykl rozwoju.",
            stage=self.current_stage,
            progress=self.progress,
        )

        return self.to_dict()

    def set_stage(
        self,
        stage: str,
    ) -> dict[str, Any]:

        normalized_stage = str(
            stage
        ).strip().upper()

        valid_stages = {
            item.value
            for item in DevelopmentCycleStage
        }

        if normalized_stage not in valid_stages:
            raise ValueError(
                f"Nieznany etap cyklu: {stage}"
            )

        self.current_stage = normalized_stage

        self.status = self.STAGE_STATUS.get(
            normalized_stage,
            self.status,
        )

        self.progress = max(
            self.progress,
            self.STAGE_PROGRESS.get(
                normalized_stage,
                self.progress,
            ),
        )

        self._touch()

        self._add_event(
            event_type="STAGE_CHANGED",
            message=(
                f"Zmieniono etap cyklu na "
                f"{normalized_stage}."
            ),
            stage=normalized_stage,
            progress=self.progress,
        )

        return self.summary()

    def next_iteration(
        self,
    ) -> dict[str, Any]:

        if self.iteration >= self.max_iterations:
            raise RuntimeError(
                "Osiągnięto maksymalną liczbę iteracji."
            )

        self.iteration += 1
        self._touch()

        self._add_event(
            event_type="ITERATION_STARTED",
            message=(
                f"Rozpoczęto iterację "
                f"{self.iteration}."
            ),
            stage=self.current_stage,
            progress=self.progress,
            metadata={
                "iteration": self.iteration,
                "max_iterations": self.max_iterations,
            },
        )

        return self.summary()

    def set_analysis(
        self,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:

        self.analysis = self._safe_dict(
            analysis
        )

        self._collect_messages(
            self.analysis
        )

        self.set_stage(
            DevelopmentCycleStage.DETECT_IMPROVEMENT.value
        )

        return dict(self.analysis)

    def set_detected_improvements(
        self,
        improvements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        self.detected_improvements = [
            dict(item)
            for item in improvements
            if isinstance(item, dict)
        ]

        self._touch()

        self._add_event(
            event_type="IMPROVEMENTS_DETECTED",
            message=(
                f"Wykryto "
                f"{len(self.detected_improvements)} "
                "możliwych ulepszeń."
            ),
            stage=self.current_stage,
            progress=self.progress,
        )

        return [
            dict(item)
            for item in self.detected_improvements
        ]

    def select_improvement(
        self,
        improvement: dict[str, Any],
    ) -> dict[str, Any]:

        self.selected_improvement = (
            self._safe_dict(
                improvement
            )
        )

        self.set_stage(
            DevelopmentCycleStage.PLAN.value
        )

        return dict(
            self.selected_improvement
        )

    def set_plan(
        self,
        plan: dict[str, Any],
    ) -> dict[str, Any]:

        self.plan = self._safe_dict(
            plan
        )

        self._collect_messages(
            self.plan
        )

        self.set_stage(
            DevelopmentCycleStage.RESEARCH.value
        )

        return dict(self.plan)

    def set_research(
        self,
        research: dict[str, Any],
    ) -> dict[str, Any]:

        self.research = self._safe_dict(
            research
        )

        self._collect_messages(
            self.research
        )

        self.set_stage(
            DevelopmentCycleStage.REASON.value
        )

        return dict(self.research)

    def set_reasoning(
        self,
        reasoning: dict[str, Any],
    ) -> dict[str, Any]:

        self.reasoning = self._safe_dict(
            reasoning
        )

        self._collect_messages(
            self.reasoning
        )

        self.set_stage(
            DevelopmentCycleStage.PREPARE_PATCH.value
        )

        return dict(self.reasoning)

    def set_patch(
        self,
        patch: dict[str, Any],
    ) -> dict[str, Any]:

        self.patch = self._safe_dict(
            patch
        )

        self._collect_messages(
            self.patch
        )

        requires_approval = bool(
            self.patch.get(
                "requires_approval",
                True,
            )
        )

        if requires_approval:
            self.set_stage(
                DevelopmentCycleStage.APPROVE.value
            )

        else:
            self.set_stage(
                DevelopmentCycleStage.EXECUTE.value
            )

        return dict(self.patch)

    def set_approval(
        self,
        approved: bool,
        note: str | None = None,
    ) -> dict[str, Any]:

        self.approval = {
            "approved": bool(approved),
            "note": (
                str(note).strip()
                if note
                else ""
            ),
            "timestamp": self._utc_now(),
        }

        if approved:
            self.set_stage(
                DevelopmentCycleStage.EXECUTE.value
            )

        else:
            self.cancel(
                reason=(
                    note
                    or "Zmiana nie została zatwierdzona."
                )
            )

        return dict(self.approval)

    def set_execution(
        self,
        execution: dict[str, Any],
    ) -> dict[str, Any]:

        self.execution = self._safe_dict(
            execution
        )

        self._collect_messages(
            self.execution
        )

        if self._detect_success(
            self.execution
        ):
            self.set_stage(
                DevelopmentCycleStage.VALIDATE.value
            )

        else:
            self.status = (
                DevelopmentCycleStatus.FAILED.value
            )
            self.result = (
                DevelopmentCycleResult.FAILED.value
            )

        self._touch()
        return dict(self.execution)

    def set_validation(
        self,
        validation: dict[str, Any],
    ) -> dict[str, Any]:

        self.validation = self._safe_dict(
            validation
        )

        self._collect_messages(
            self.validation
        )

        if self._detect_success(
            self.validation
        ):
            self.set_stage(
                DevelopmentCycleStage.REPORT.value
            )

        else:
            self.set_stage(
                DevelopmentCycleStage.ROLLBACK.value
            )

        return dict(self.validation)

    def set_rollback(
        self,
        rollback: dict[str, Any],
    ) -> dict[str, Any]:

        self.rollback = self._safe_dict(
            rollback
        )

        self._collect_messages(
            self.rollback
        )

        rollback_success = self._detect_success(
            self.rollback
        )

        if rollback_success:
            self.result = (
                DevelopmentCycleResult.ROLLED_BACK.value
            )
        else:
            self.result = (
                DevelopmentCycleResult.FAILED.value
            )

        self.set_stage(
            DevelopmentCycleStage.REPORT.value
        )

        return dict(self.rollback)

    def set_report(
        self,
        report: dict[str, Any],
    ) -> dict[str, Any]:

        self.report = self._safe_dict(
            report
        )

        self._collect_messages(
            self.report
        )

        return dict(self.report)

    def complete(
        self,
        result: str = DevelopmentCycleResult.SUCCESS.value,
        report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_result = str(
            result
        ).strip().upper()

        valid_results = {
            item.value
            for item in DevelopmentCycleResult
        }

        if normalized_result not in valid_results:
            normalized_result = (
                DevelopmentCycleResult.SUCCESS.value
            )

        if report is not None:
            self.report = self._safe_dict(
                report
            )

        self.status = (
            DevelopmentCycleStatus.COMPLETED.value
        )
        self.result = normalized_result
        self.progress = 1.0
        self.completed_at = self._utc_now()
        self.current_stage = (
            DevelopmentCycleStage.REPORT.value
        )

        self._touch()

        self._add_event(
            event_type="COMPLETED",
            message=(
                f"Cykl zakończono wynikiem "
                f"{self.result}."
            ),
            stage=self.current_stage,
            progress=1.0,
        )

        return self.to_dict()

    def fail(
        self,
        error: str,
        report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_error = str(
            error
        ).strip()

        if normalized_error:
            self.errors = self._unique_strings(
                self.errors
                + [normalized_error]
            )

        if report is not None:
            self.report = self._safe_dict(
                report
            )

        self.status = DevelopmentCycleStatus.FAILED.value
        self.result = DevelopmentCycleResult.FAILED.value
        self.completed_at = self._utc_now()

        self._touch()

        self._add_event(
            event_type="FAILED",
            message=(
                normalized_error
                or "Cykl zakończył się błędem."
            ),
            stage=self.current_stage,
            progress=self.progress,
        )

        return self.to_dict()

    def cancel(
        self,
        reason: str | None = None,
    ) -> dict[str, Any]:

        self.status = (
            DevelopmentCycleStatus.CANCELLED.value
        )
        self.result = (
            DevelopmentCycleResult.CANCELLED.value
        )
        self.completed_at = self._utc_now()

        if reason:
            self.warnings = self._unique_strings(
                self.warnings
                + [str(reason).strip()]
            )

        self._touch()

        self._add_event(
            event_type="CANCELLED",
            message=(
                str(reason).strip()
                if reason
                else "Cykl został anulowany."
            ),
            stage=self.current_stage,
            progress=self.progress,
        )

        return self.to_dict()

    def add_warning(
        self,
        warning: str,
    ) -> list[str]:

        normalized = str(
            warning
        ).strip()

        if normalized:
            self.warnings = self._unique_strings(
                self.warnings
                + [normalized]
            )

        self._touch()
        return list(self.warnings)

    def add_lesson(
        self,
        lesson: str,
    ) -> list[str]:

        normalized = str(
            lesson
        ).strip()

        if normalized:
            self.lessons = self._unique_strings(
                self.lessons
                + [normalized]
            )

        self._touch()
        return list(self.lessons)

    def can_continue(
        self,
    ) -> bool:

        return (
            self.iteration < self.max_iterations
            and self.status
            not in {
                DevelopmentCycleStatus.COMPLETED.value,
                DevelopmentCycleStatus.FAILED.value,
                DevelopmentCycleStatus.CANCELLED.value,
            }
        )

    def summary(
        self,
    ) -> dict[str, Any]:

        return {
            "cycle_id": self.cycle_id,
            "project_root": self.project_root,
            "objective": self.objective,
            "status": self.status,
            "current_stage": self.current_stage,
            "result": self.result,
            "progress": round(
                self.progress,
                4,
            ),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "improvements_count": len(
                self.detected_improvements
            ),
            "selected_improvement": (
                self.selected_improvement.get(
                    "title",
                    self.selected_improvement.get(
                        "name"
                    ),
                )
                if self.selected_improvement
                else None
            ),
            "errors_count": len(
                self.errors
            ),
            "warnings_count": len(
                self.warnings
            ),
            "lessons_count": len(
                self.lessons
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return DevelopmentCycleData(
            cycle_id=self.cycle_id,
            project_root=self.project_root,
            objective=self.objective,
            status=self.status,
            current_stage=self.current_stage,
            result=self.result,
            progress=round(
                self.progress,
                4,
            ),
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            analysis=dict(self.analysis),
            detected_improvements=[
                dict(item)
                for item in self.detected_improvements
            ],
            selected_improvement=dict(
                self.selected_improvement
            ),
            plan=dict(self.plan),
            research=dict(self.research),
            reasoning=dict(self.reasoning),
            patch=dict(self.patch),
            approval=dict(self.approval),
            execution=dict(self.execution),
            validation=dict(self.validation),
            rollback=dict(self.rollback),
            report=dict(self.report),
            events=[
                event.to_dict()
                for event in self.events
            ],
            errors=list(self.errors),
            warnings=list(self.warnings),
            lessons=list(self.lessons),
            metadata=dict(self.metadata),
        ).to_dict()

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DevelopmentCycle:

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "DevelopmentCycle.from_dict wymaga dict."
            )

        cycle = cls(
            project_root=str(
                data.get(
                    "project_root",
                    "",
                )
            ),
            objective=str(
                data.get(
                    "objective",
                    "",
                )
            ),
            max_iterations=int(
                data.get(
                    "max_iterations",
                    10,
                )
            ),
            cycle_id=str(
                data.get(
                    "cycle_id",
                    "",
                )
            ),
            metadata=(
                data.get("metadata")
                if isinstance(
                    data.get("metadata"),
                    dict,
                )
                else {}
            ),
        )

        cycle.status = str(
            data.get(
                "status",
                DevelopmentCycleStatus.CREATED.value,
            )
        ).upper()

        cycle.current_stage = (
            cycle._optional_string(
                data.get(
                    "current_stage"
                )
            )
        )

        cycle.result = str(
            data.get(
                "result",
                DevelopmentCycleResult.UNKNOWN.value,
            )
        ).upper()

        cycle.progress = max(
            0.0,
            min(
                1.0,
                cycle._safe_float(
                    data.get(
                        "progress",
                        0.0,
                    ),
                    0.0,
                ),
            ),
        )

        cycle.iteration = max(
            0,
            int(
                data.get(
                    "iteration",
                    0,
                )
            ),
        )

        cycle.created_at = str(
            data.get(
                "created_at",
                cycle.created_at,
            )
        )

        cycle.updated_at = str(
            data.get(
                "updated_at",
                cycle.updated_at,
            )
        )

        cycle.started_at = (
            cycle._optional_string(
                data.get(
                    "started_at"
                )
            )
        )

        cycle.completed_at = (
            cycle._optional_string(
                data.get(
                    "completed_at"
                )
            )
        )

        cycle.analysis = cycle._safe_dict(
            data.get("analysis")
        )

        cycle.detected_improvements = [
            dict(item)
            for item in cycle._safe_list(
                data.get(
                    "detected_improvements",
                    [],
                )
            )
            if isinstance(item, dict)
        ]

        cycle.selected_improvement = (
            cycle._safe_dict(
                data.get(
                    "selected_improvement"
                )
            )
        )

        cycle.plan = cycle._safe_dict(
            data.get("plan")
        )
        cycle.research = cycle._safe_dict(
            data.get("research")
        )
        cycle.reasoning = cycle._safe_dict(
            data.get("reasoning")
        )
        cycle.patch = cycle._safe_dict(
            data.get("patch")
        )
        cycle.approval = cycle._safe_dict(
            data.get("approval")
        )
        cycle.execution = cycle._safe_dict(
            data.get("execution")
        )
        cycle.validation = cycle._safe_dict(
            data.get("validation")
        )
        cycle.rollback = cycle._safe_dict(
            data.get("rollback")
        )
        cycle.report = cycle._safe_dict(
            data.get("report")
        )

        cycle.events = []

        for raw_event in cycle._safe_list(
            data.get(
                "events",
                [],
            )
        ):
            if not isinstance(
                raw_event,
                dict,
            ):
                continue

            cycle.events.append(
                CycleEvent(
                    event_id=str(
                        raw_event.get(
                            "event_id",
                            f"cycle_event_{uuid4().hex}",
                        )
                    ),
                    event_type=str(
                        raw_event.get(
                            "event_type",
                            "UNKNOWN",
                        )
                    ),
                    message=str(
                        raw_event.get(
                            "message",
                            "",
                        )
                    ),
                    timestamp=str(
                        raw_event.get(
                            "timestamp",
                            cycle._utc_now(),
                        )
                    ),
                    stage=cycle._optional_string(
                        raw_event.get(
                            "stage"
                        )
                    ),
                    progress=(
                        cycle._safe_float(
                            raw_event.get(
                                "progress"
                            ),
                            0.0,
                        )
                        if raw_event.get(
                            "progress"
                        )
                        is not None
                        else None
                    ),
                    metadata=cycle._safe_dict(
                        raw_event.get(
                            "metadata"
                        )
                    ),
                )
            )

        cycle.errors = cycle._unique_strings(
            cycle._safe_list(
                data.get(
                    "errors",
                    [],
                )
            )
        )

        cycle.warnings = cycle._unique_strings(
            cycle._safe_list(
                data.get(
                    "warnings",
                    [],
                )
            )
        )

        cycle.lessons = cycle._unique_strings(
            cycle._safe_list(
                data.get(
                    "lessons",
                    [],
                )
            )
        )

        return cycle

    def _collect_messages(
        self,
        data: dict[str, Any],
    ) -> None:

        errors = self._safe_list(
            data.get(
                "errors",
                [],
            )
        )

        warnings = self._safe_list(
            data.get(
                "warnings",
                [],
            )
        )

        lessons = self._safe_list(
            data.get(
                "lessons",
                [],
            )
        )

        error = data.get(
            "error"
        )

        if error:
            errors.append(error)

        self.errors = self._unique_strings(
            self.errors + errors
        )

        self.warnings = self._unique_strings(
            self.warnings + warnings
        )

        self.lessons = self._unique_strings(
            self.lessons + lessons
        )

    def _detect_success(
        self,
        data: dict[str, Any],
    ) -> bool:

        value = data.get(
            "success"
        )

        if isinstance(
            value,
            bool,
        ):
            return value

        status = str(
            data.get(
                "status",
                "",
            )
        ).upper()

        return status in {
            "SUCCESS",
            "COMPLETED",
            "DONE",
            "VALIDATED",
            "PASSED",
        }

    def _add_event(
        self,
        event_type: str,
        message: str,
        stage: str | None = None,
        progress: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        self.events.append(
            CycleEvent(
                event_id=f"cycle_event_{uuid4().hex}",
                event_type=str(
                    event_type
                ).upper(),
                message=str(
                    message
                ),
                timestamp=self._utc_now(),
                stage=stage,
                progress=progress,
                metadata=self._safe_dict(
                    metadata
                ),
            )
        )

        self._touch()

    def _touch(
        self,
    ) -> None:

        self.updated_at = self._utc_now()

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

        if isinstance(
            value,
            dict,
        ):
            return dict(value)

        return {}

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None

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

            seen.add(key)
            result.append(text)

        return result

    def _utc_now(
        self,
    ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

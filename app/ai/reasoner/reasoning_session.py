from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ReasoningSessionStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_FOR_RESEARCH = "WAITING_FOR_RESEARCH"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    ROLLING_BACK = "ROLLING_BACK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ReasoningStepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass
class ReasoningStep:
    step_id: str
    name: str
    step_type: str
    order: int
    status: str = ReasoningStepStatus.PENDING.value
    required: bool = True
    started_at: str | None = None
    completed_at: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReasoningSessionData:
    session_id: str
    status: str
    created_at: str
    updated_at: str
    user_request: str
    goal: dict[str, Any]
    decision_graph: dict[str, Any]
    options_result: dict[str, Any]
    risk_result: dict[str, Any]
    strategy: dict[str, Any]
    research_context: dict[str, Any]
    execution: dict[str, Any]
    validation: dict[str, Any]
    rollback: dict[str, Any]
    result: dict[str, Any]
    steps: list[dict[str, Any]]
    current_step_id: str | None
    approved: bool | None
    success: bool | None
    confidence: float
    errors: list[str]
    lessons: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReasoningSession:

    def __init__(
        self,
        user_request: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        now = self._utc_now()

        self.session_id = (
            session_id.strip()
            if isinstance(session_id, str)
            and session_id.strip()
            else f"reasoning_session_{uuid4().hex}"
        )

        self.status = ReasoningSessionStatus.CREATED.value
        self.created_at = now
        self.updated_at = now
        self.user_request = str(user_request).strip()

        self.goal: dict[str, Any] = {}
        self.decision_graph: dict[str, Any] = {}
        self.options_result: dict[str, Any] = {}
        self.risk_result: dict[str, Any] = {}
        self.strategy: dict[str, Any] = {}
        self.research_context: dict[str, Any] = {}
        self.execution: dict[str, Any] = {}
        self.validation: dict[str, Any] = {}
        self.rollback: dict[str, Any] = {}
        self.result: dict[str, Any] = {}

        self._steps: list[ReasoningStep] = []
        self.current_step_id: str | None = None

        self.approved: bool | None = None
        self.success: bool | None = None
        self.confidence: float = 0.0

        self.errors: list[str] = []
        self.lessons: list[str] = []

        self.metadata: dict[str, Any] = {
            "session_version": "1.0.0",
            **(metadata or {}),
        }

    def start(self) -> dict[str, Any]:
        self.status = ReasoningSessionStatus.RUNNING.value
        self._touch()
        return self.to_dict()

    def set_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:
        self.goal = self._safe_dict(goal)
        self._update_confidence(
            self.goal.get("confidence")
        )
        self._touch()
        return self.goal

    def set_decision_graph(
        self,
        decision_graph: dict[str, Any],
    ) -> dict[str, Any]:
        self.decision_graph = self._safe_dict(
            decision_graph
        )
        self._touch()
        return self.decision_graph

    def set_options_result(
        self,
        options_result: dict[str, Any],
    ) -> dict[str, Any]:
        self.options_result = self._safe_dict(
            options_result
        )
        self._touch()
        return self.options_result

    def set_risk_result(
        self,
        risk_result: dict[str, Any],
    ) -> dict[str, Any]:
        self.risk_result = self._safe_dict(
            risk_result
        )

        recommended_id = self.risk_result.get(
            "recommended_option_id"
        )

        if recommended_id:
            self.metadata["recommended_option_id"] = (
                recommended_id
            )

        self._touch()
        return self.risk_result

    def set_strategy(
        self,
        strategy: dict[str, Any],
    ) -> dict[str, Any]:
        self.strategy = self._safe_dict(strategy)

        self._update_confidence(
            self.strategy.get("confidence")
        )

        strategy_status = str(
            self.strategy.get(
                "status",
                "",
            )
        ).upper()

        if strategy_status == "BLOCKED":
            self.status = (
                ReasoningSessionStatus.FAILED.value
            )

        elif strategy_status == "REJECTED":
            self.status = (
                ReasoningSessionStatus.REJECTED.value
            )

        elif self.strategy.get(
            "requires_research",
            False,
        ) and not self.research_context:
            self.status = (
                ReasoningSessionStatus
                .WAITING_FOR_RESEARCH
                .value
            )

        elif self.strategy.get(
            "requires_confirmation",
            False,
        ) and self.approved is not True:
            self.status = (
                ReasoningSessionStatus
                .WAITING_FOR_CONFIRMATION
                .value
            )

        else:
            self.status = (
                ReasoningSessionStatus
                .READY_FOR_EXECUTION
                .value
            )

        self._touch()
        return self.strategy

    def set_research_context(
        self,
        research_context: dict[str, Any],
    ) -> dict[str, Any]:
        self.research_context = self._safe_dict(
            research_context
        )

        if (
            self.status
            == ReasoningSessionStatus
            .WAITING_FOR_RESEARCH
            .value
        ):
            if self.strategy.get(
                "requires_confirmation",
                False,
            ) and self.approved is not True:
                self.status = (
                    ReasoningSessionStatus
                    .WAITING_FOR_CONFIRMATION
                    .value
                )
            else:
                self.status = (
                    ReasoningSessionStatus
                    .READY_FOR_EXECUTION
                    .value
                )

        self._touch()
        return self.research_context

    def approve(
        self,
        approved: bool,
        note: str | None = None,
    ) -> dict[str, Any]:
        self.approved = bool(approved)

        if note:
            self.metadata["approval_note"] = str(note)

        if self.approved:
            self.status = (
                ReasoningSessionStatus
                .READY_FOR_EXECUTION
                .value
            )
        else:
            self.status = (
                ReasoningSessionStatus.REJECTED.value
            )
            self.success = False

        self.metadata["approved_at"] = self._utc_now()
        self._touch()

        return {
            "approved": self.approved,
            "status": self.status,
            "note": note,
        }

    def add_step(
        self,
        name: str,
        step_type: str,
        order: int | None = None,
        required: bool = True,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_order = (
            int(order)
            if order is not None
            else len(self._steps) + 1
        )

        step = ReasoningStep(
            step_id=f"reasoning_step_{uuid4().hex}",
            name=str(name).strip(),
            step_type=str(step_type).strip().upper(),
            order=max(1, normalized_order),
            required=bool(required),
            input_data=self._safe_dict(input_data),
            metadata=self._safe_dict(metadata),
        )

        self._steps.append(step)
        self._steps.sort(
            key=lambda item: item.order
        )

        self._touch()
        return step.to_dict()

    def load_strategy_phases(
        self,
    ) -> list[dict[str, Any]]:

        phases = self.strategy.get(
            "phases",
            []
        )

        if not isinstance(phases, list):
            return []

        self._steps = []

        for index, phase in enumerate(
            phases,
            start=1,
        ):
            if not isinstance(phase, dict):
                continue

            self.add_step(
                name=str(
                    phase.get(
                        "name",
                        f"Faza {index}",
                    )
                ),
                step_type=str(
                    phase.get(
                        "phase_type",
                        "UNKNOWN",
                    )
                ),
                order=self._safe_int(
                    phase.get("order"),
                    index,
                ),
                required=bool(
                    phase.get(
                        "required",
                        True,
                    )
                ),
                input_data=self._safe_dict(
                    phase.get(
                        "input_data",
                        {},
                    )
                ),
                metadata={
                    "phase_id": phase.get(
                        "phase_id"
                    ),
                    "can_skip": phase.get(
                        "can_skip",
                        False,
                    ),
                    "expected_output": (
                        self._safe_dict(
                            phase.get(
                                "expected_output",
                                {},
                            )
                        )
                    ),
                    "success_conditions": (
                        self._safe_list(
                            phase.get(
                                "success_conditions",
                                [],
                            )
                        )
                    ),
                    "failure_actions": (
                        self._safe_list(
                            phase.get(
                                "failure_actions",
                                [],
                            )
                        )
                    ),
                },
            )

        self._touch()

        return [
            step.to_dict()
            for step in self._steps
        ]

    def start_step(
        self,
        step_id: str,
    ) -> dict[str, Any] | None:

        step = self._find_step(step_id)

        if step is None:
            return None

        if step.status not in {
            ReasoningStepStatus.PENDING.value,
            ReasoningStepStatus.BLOCKED.value,
        }:
            return step.to_dict()

        for existing_step in self._steps:
            if (
                existing_step.status
                == ReasoningStepStatus.RUNNING.value
            ):
                existing_step.status = (
                    ReasoningStepStatus.PENDING.value
                )
                existing_step.started_at = None

        step.status = ReasoningStepStatus.RUNNING.value
        step.started_at = self._utc_now()
        step.completed_at = None

        self.current_step_id = step.step_id
        self.status = self._status_for_step(
            step.step_type
        )

        self._touch()
        return step.to_dict()

    def complete_step(
        self,
        step_id: str,
        output_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        step = self._find_step(step_id)

        if step is None:
            return None

        step.status = ReasoningStepStatus.COMPLETED.value
        step.completed_at = self._utc_now()
        step.output_data = self._safe_dict(
            output_data
        )

        if self.current_step_id == step.step_id:
            self.current_step_id = None

        self._touch()
        self._refresh_status_after_step()

        return step.to_dict()

    def fail_step(
        self,
        step_id: str,
        error: str,
        output_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        step = self._find_step(step_id)

        if step is None:
            return None

        normalized_error = str(error).strip()

        step.status = ReasoningStepStatus.FAILED.value
        step.completed_at = self._utc_now()
        step.output_data = self._safe_dict(
            output_data
        )

        if normalized_error:
            step.errors.append(normalized_error)
            self.add_error(normalized_error)

        if self.current_step_id == step.step_id:
            self.current_step_id = None

        self.status = ReasoningSessionStatus.FAILED.value
        self.success = False

        self._touch()
        return step.to_dict()

    def skip_step(
        self,
        step_id: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:

        step = self._find_step(step_id)

        if step is None:
            return None

        step.status = ReasoningStepStatus.SKIPPED.value
        step.completed_at = self._utc_now()

        if reason:
            step.metadata["skip_reason"] = str(reason)

        if self.current_step_id == step.step_id:
            self.current_step_id = None

        self._touch()
        self._refresh_status_after_step()

        return step.to_dict()

    def block_step(
        self,
        step_id: str,
        reason: str,
    ) -> dict[str, Any] | None:

        step = self._find_step(step_id)

        if step is None:
            return None

        step.status = ReasoningStepStatus.BLOCKED.value
        step.errors = self._unique_strings(
            step.errors + [reason]
        )

        self.add_error(reason)
        self._touch()

        return step.to_dict()

    def next_pending_step(
        self,
    ) -> dict[str, Any] | None:

        for step in sorted(
            self._steps,
            key=lambda item: item.order,
        ):
            if (
                step.status
                == ReasoningStepStatus.PENDING.value
            ):
                return step.to_dict()

        return None

    def set_execution(
        self,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        self.execution = self._safe_dict(
            execution
        )

        status = str(
            self.execution.get(
                "status",
                "",
            )
        ).upper()

        if status in {
            "RUNNING",
            "EXECUTING",
        }:
            self.status = (
                ReasoningSessionStatus.EXECUTING.value
            )

        if status in {
            "FAILED",
            "ERROR",
        }:
            self.status = (
                ReasoningSessionStatus.FAILED.value
            )
            self.success = False

        self._collect_errors_from_dict(
            self.execution
        )

        self._touch()
        return self.execution

    def set_validation(
        self,
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        self.validation = self._safe_dict(
            validation
        )

        self.status = (
            ReasoningSessionStatus.VALIDATING.value
        )

        validation_success = self._extract_bool(
            self.validation,
            [
                "success",
                "valid",
                "passed",
            ],
        )

        if validation_success is False:
            self.success = False

        self._collect_errors_from_dict(
            self.validation
        )

        self._touch()
        return self.validation

    def set_rollback(
        self,
        rollback: dict[str, Any],
    ) -> dict[str, Any]:
        self.rollback = self._safe_dict(
            rollback
        )

        self.status = (
            ReasoningSessionStatus.ROLLING_BACK.value
        )

        self._collect_errors_from_dict(
            self.rollback
        )

        self._touch()
        return self.rollback

    def complete(
        self,
        result: dict[str, Any] | None = None,
        success: bool | None = None,
    ) -> dict[str, Any]:

        self.result = self._safe_dict(result)

        detected_success = (
            success
            if isinstance(success, bool)
            else self._detect_success(
                self.result
            )
        )

        if detected_success is None:
            detected_success = not bool(
                self.errors
            )

        self.success = bool(detected_success)

        self.status = (
            ReasoningSessionStatus.COMPLETED.value
            if self.success
            else ReasoningSessionStatus.FAILED.value
        )

        self._collect_errors_from_dict(
            self.result
        )

        lessons = self._safe_list(
            self.result.get(
                "lessons",
                [],
            )
        )

        self.lessons = self._unique_strings(
            self.lessons + lessons
        )

        self.metadata["completed_at"] = self._utc_now()
        self.current_step_id = None

        self._touch()
        return self.to_dict()

    def cancel(
        self,
        reason: str | None = None,
    ) -> dict[str, Any]:

        self.status = (
            ReasoningSessionStatus.CANCELLED.value
        )
        self.success = False

        if reason:
            self.add_error(
                f"Sesja anulowana: {reason}"
            )

        self.metadata["cancelled_at"] = self._utc_now()
        self.current_step_id = None

        self._touch()
        return self.to_dict()

    def add_error(
        self,
        error: str,
    ) -> list[str]:

        normalized = str(error).strip()

        if normalized:
            self.errors = self._unique_strings(
                self.errors + [normalized]
            )

        self._touch()
        return list(self.errors)

    def add_lesson(
        self,
        lesson: str,
    ) -> list[str]:

        normalized = str(lesson).strip()

        if normalized:
            self.lessons = self._unique_strings(
                self.lessons + [normalized]
            )

        self._touch()
        return list(self.lessons)

    def get_step(
        self,
        step_id: str,
    ) -> dict[str, Any] | None:

        step = self._find_step(step_id)

        if step is None:
            return None

        return step.to_dict()

    def get_steps(
        self,
        status: str | None = None,
        step_type: str | None = None,
    ) -> list[dict[str, Any]]:

        normalized_status = (
            str(status).upper()
            if status is not None
            else None
        )

        normalized_type = (
            str(step_type).upper()
            if step_type is not None
            else None
        )

        result: list[dict[str, Any]] = []

        for step in sorted(
            self._steps,
            key=lambda item: item.order,
        ):
            if (
                normalized_status is not None
                and step.status != normalized_status
            ):
                continue

            if (
                normalized_type is not None
                and step.step_type != normalized_type
            ):
                continue

            result.append(
                step.to_dict()
            )

        return result

    def summary(
        self,
    ) -> dict[str, Any]:

        counts = {
            status.value: 0
            for status in ReasoningStepStatus
        }

        for step in self._steps:
            counts[step.status] = (
                counts.get(
                    step.status,
                    0,
                )
                + 1
            )

        return {
            "session_id": self.session_id,
            "status": self.status,
            "user_request": self.user_request,
            "goal_type": self.goal.get(
                "goal_type",
                "UNKNOWN",
            ),
            "strategy_id": self.strategy.get(
                "strategy_id"
            ),
            "selected_option_id": (
                self.strategy.get(
                    "selected_option",
                    {},
                ).get(
                    "option_id"
                )
            ),
            "risk_level": (
                self.strategy.get(
                    "risk_assessment",
                    {},
                ).get(
                    "risk_level",
                    "UNKNOWN",
                )
            ),
            "approved": self.approved,
            "success": self.success,
            "confidence": round(
                self.confidence,
                2,
            ),
            "current_step_id": self.current_step_id,
            "steps_count": len(self._steps),
            "step_status_counts": counts,
            "errors_count": len(self.errors),
            "lessons_count": len(self.lessons),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        data = ReasoningSessionData(
            session_id=self.session_id,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            user_request=self.user_request,
            goal=dict(self.goal),
            decision_graph=dict(
                self.decision_graph
            ),
            options_result=dict(
                self.options_result
            ),
            risk_result=dict(
                self.risk_result
            ),
            strategy=dict(self.strategy),
            research_context=dict(
                self.research_context
            ),
            execution=dict(self.execution),
            validation=dict(self.validation),
            rollback=dict(self.rollback),
            result=dict(self.result),
            steps=[
                step.to_dict()
                for step in sorted(
                    self._steps,
                    key=lambda item: item.order,
                )
            ],
            current_step_id=self.current_step_id,
            approved=self.approved,
            success=self.success,
            confidence=round(
                self.confidence,
                2,
            ),
            errors=list(self.errors),
            lessons=list(self.lessons),
            metadata=dict(self.metadata),
        )

        return data.to_dict()

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ReasoningSession:

        if not isinstance(data, dict):
            raise TypeError(
                "ReasoningSession.from_dict wymaga dict."
            )

        session = cls(
            user_request=str(
                data.get(
                    "user_request",
                    "",
                )
            ),
            session_id=str(
                data.get(
                    "session_id",
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

        session.status = str(
            data.get(
                "status",
                ReasoningSessionStatus.CREATED.value,
            )
        )
        session.created_at = str(
            data.get(
                "created_at",
                session.created_at,
            )
        )
        session.updated_at = str(
            data.get(
                "updated_at",
                session.updated_at,
            )
        )

        session.goal = session._safe_dict(
            data.get("goal")
        )
        session.decision_graph = (
            session._safe_dict(
                data.get("decision_graph")
            )
        )
        session.options_result = (
            session._safe_dict(
                data.get("options_result")
            )
        )
        session.risk_result = (
            session._safe_dict(
                data.get("risk_result")
            )
        )
        session.strategy = session._safe_dict(
            data.get("strategy")
        )
        session.research_context = (
            session._safe_dict(
                data.get("research_context")
            )
        )
        session.execution = session._safe_dict(
            data.get("execution")
        )
        session.validation = session._safe_dict(
            data.get("validation")
        )
        session.rollback = session._safe_dict(
            data.get("rollback")
        )
        session.result = session._safe_dict(
            data.get("result")
        )

        session.current_step_id = (
            str(data["current_step_id"])
            if data.get("current_step_id")
            is not None
            else None
        )

        session.approved = session._optional_bool(
            data.get("approved")
        )
        session.success = session._optional_bool(
            data.get("success")
        )
        session.confidence = max(
            0.0,
            min(
                1.0,
                session._safe_float(
                    data.get(
                        "confidence",
                        0.0,
                    ),
                    0.0,
                ),
            ),
        )

        session.errors = session._unique_strings(
            session._safe_list(
                data.get(
                    "errors",
                    [],
                )
            )
        )
        session.lessons = session._unique_strings(
            session._safe_list(
                data.get(
                    "lessons",
                    [],
                )
            )
        )

        raw_steps = data.get(
            "steps",
            []
        )

        if isinstance(raw_steps, list):
            for index, raw_step in enumerate(
                raw_steps,
                start=1,
            ):
                if not isinstance(
                    raw_step,
                    dict,
                ):
                    continue

                step = ReasoningStep(
                    step_id=str(
                        raw_step.get(
                            "step_id",
                            (
                                "reasoning_step_"
                                f"{uuid4().hex}"
                            ),
                        )
                    ),
                    name=str(
                        raw_step.get(
                            "name",
                            f"Krok {index}",
                        )
                    ),
                    step_type=str(
                        raw_step.get(
                            "step_type",
                            "UNKNOWN",
                        )
                    ).upper(),
                    order=session._safe_int(
                        raw_step.get("order"),
                        index,
                    ),
                    status=str(
                        raw_step.get(
                            "status",
                            ReasoningStepStatus
                            .PENDING
                            .value,
                        )
                    ).upper(),
                    required=bool(
                        raw_step.get(
                            "required",
                            True,
                        )
                    ),
                    started_at=(
                        str(raw_step["started_at"])
                        if raw_step.get(
                            "started_at"
                        ) is not None
                        else None
                    ),
                    completed_at=(
                        str(
                            raw_step[
                                "completed_at"
                            ]
                        )
                        if raw_step.get(
                            "completed_at"
                        ) is not None
                        else None
                    ),
                    input_data=session._safe_dict(
                        raw_step.get(
                            "input_data"
                        )
                    ),
                    output_data=session._safe_dict(
                        raw_step.get(
                            "output_data"
                        )
                    ),
                    errors=session._unique_strings(
                        session._safe_list(
                            raw_step.get(
                                "errors",
                                [],
                            )
                        )
                    ),
                    metadata=session._safe_dict(
                        raw_step.get(
                            "metadata"
                        )
                    ),
                )

                session._steps.append(step)

        session._steps.sort(
            key=lambda item: item.order
        )

        return session

    def _refresh_status_after_step(
        self,
    ) -> None:

        required_steps = [
            step
            for step in self._steps
            if step.required
        ]

        if not required_steps:
            return

        if any(
            step.status
            == ReasoningStepStatus.FAILED.value
            for step in required_steps
        ):
            self.status = (
                ReasoningSessionStatus.FAILED.value
            )
            self.success = False
            return

        if all(
            step.status
            in {
                ReasoningStepStatus.COMPLETED.value,
                ReasoningStepStatus.SKIPPED.value,
            }
            for step in required_steps
        ):
            self.status = (
                ReasoningSessionStatus.COMPLETED.value
            )

            if self.success is None:
                self.success = True

    def _status_for_step(
        self,
        step_type: str,
    ) -> str:

        normalized = str(
            step_type
        ).upper()

        if normalized == "RESEARCH":
            return (
                ReasoningSessionStatus
                .WAITING_FOR_RESEARCH
                .value
            )

        if normalized == "CONFIRM":
            return (
                ReasoningSessionStatus
                .WAITING_FOR_CONFIRMATION
                .value
            )

        if normalized in {
            "EXECUTE",
            "BACKUP",
            "PREVIEW",
        }:
            return (
                ReasoningSessionStatus.EXECUTING.value
            )

        if normalized == "VALIDATE":
            return (
                ReasoningSessionStatus.VALIDATING.value
            )

        if normalized == "ROLLBACK":
            return (
                ReasoningSessionStatus.ROLLING_BACK.value
            )

        return ReasoningSessionStatus.RUNNING.value

    def _find_step(
        self,
        step_id: str,
    ) -> ReasoningStep | None:

        normalized = str(step_id).strip()

        for step in self._steps:
            if step.step_id == normalized:
                return step

        return None

    def _update_confidence(
        self,
        value: Any,
    ) -> None:

        confidence = self._safe_float(
            value,
            self.confidence,
        )

        self.confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

    def _detect_success(
        self,
        data: dict[str, Any],
    ) -> bool | None:

        for key in [
            "success",
            "valid",
            "passed",
        ]:
            value = data.get(key)

            if isinstance(value, bool):
                return value

        status = str(
            data.get(
                "status",
                "",
            )
        ).upper()

        if status in {
            "SUCCESS",
            "COMPLETED",
            "DONE",
            "VALIDATED",
        }:
            return True

        if status in {
            "FAILED",
            "ERROR",
            "REJECTED",
            "ROLLED_BACK",
        }:
            return False

        return None

    def _collect_errors_from_dict(
        self,
        data: dict[str, Any],
    ) -> None:

        errors = self._safe_list(
            data.get(
                "errors",
                [],
            )
        )

        error = data.get("error")

        if error:
            errors.append(error)

        status = str(
            data.get(
                "status",
                "",
            )
        ).upper()

        message = data.get("message")

        if (
            message
            and status in {
                "FAILED",
                "ERROR",
                "REJECTED",
            }
        ):
            errors.append(message)

        self.errors = self._unique_strings(
            self.errors + errors
        )

    def _extract_bool(
        self,
        data: dict[str, Any],
        keys: list[str],
    ) -> bool | None:

        for key in keys:
            if key not in data:
                continue

            value = data[key]

            if isinstance(value, bool):
                return value

            parsed = self._optional_bool(
                value
            )

            if parsed is not None:
                return parsed

        return None

    def _optional_bool(
        self,
        value: Any,
    ) -> bool | None:

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            normalized = value.strip().lower()

            if normalized in {
                "true",
                "yes",
                "tak",
                "1",
            }:
                return True

            if normalized in {
                "false",
                "no",
                "nie",
                "0",
            }:
                return False

        return None

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

    def _touch(
        self,
    ) -> None:

        self.updated_at = self._utc_now()

    def _utc_now(
        self,
    ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class PlanningSessionStatus(str, Enum):
    CREATED = "CREATED"
    BUILDING = "BUILDING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PlanningStepStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class PlanningStep:
    step_id: str
    goal_id: str
    name: str
    order: int
    status: str
    progress: float
    dependencies: list[str]
    started_at: str | None
    completed_at: str | None
    output: dict[str, Any]
    errors: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanningSessionData:
    session_id: str
    root_goal_id: str
    title: str
    status: str
    progress: float
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None
    goal: dict[str, Any]
    decomposition: dict[str, Any]
    graph: dict[str, Any]
    priority_result: dict[str, Any]
    schedule: dict[str, Any]
    execution: dict[str, Any]
    result: dict[str, Any]
    steps: list[dict[str, Any]]
    current_step_id: str | None
    next_goal_id: str | None
    active_goal_ids: list[str]
    completed_goal_ids: list[str]
    blocked_goal_ids: list[str]
    errors: list[str]
    lessons: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlanningSession:

    def __init__(
        self,
        root_goal_id: str,
        title: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        now = self._utc_now()

        self.session_id = (
            str(session_id).strip()
            if session_id
            else f"planning_session_{uuid4().hex}"
        )

        self.root_goal_id = str(
            root_goal_id
        ).strip()

        self.title = str(title).strip()

        self.status = PlanningSessionStatus.CREATED.value
        self.progress = 0.0
        self.created_at = now
        self.updated_at = now
        self.started_at: str | None = None
        self.completed_at: str | None = None

        self.goal: dict[str, Any] = {}
        self.decomposition: dict[str, Any] = {}
        self.graph: dict[str, Any] = {}
        self.priority_result: dict[str, Any] = {}
        self.schedule: dict[str, Any] = {}
        self.execution: dict[str, Any] = {}
        self.result: dict[str, Any] = {}

        self._steps: list[PlanningStep] = []
        self.current_step_id: str | None = None
        self.next_goal_id: str | None = None

        self.active_goal_ids: list[str] = []
        self.completed_goal_ids: list[str] = []
        self.blocked_goal_ids: list[str] = []

        self.errors: list[str] = []
        self.lessons: list[str] = []

        self.metadata: dict[str, Any] = {
            "planning_session_version": "1.0.0",
            **(metadata or {}),
        }

    def start_building(
        self,
    ) -> dict[str, Any]:

        self.status = PlanningSessionStatus.BUILDING.value
        self.started_at = self.started_at or self._utc_now()
        self._touch()
        return self.to_dict()

    def set_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        self.goal = self._safe_dict(goal)

        if not self.root_goal_id:
            self.root_goal_id = str(
                self.goal.get(
                    "goal_id",
                    "",
                )
            )

        if not self.title:
            self.title = str(
                self.goal.get(
                    "title",
                    "",
                )
            )

        self._touch()
        return dict(self.goal)

    def set_decomposition(
        self,
        decomposition: dict[str, Any],
    ) -> dict[str, Any]:

        self.decomposition = self._safe_dict(
            decomposition
        )

        subgoals = self.decomposition.get(
            "subgoals",
            [],
        )

        if isinstance(subgoals, list):
            self._steps = []

            for index, subgoal in enumerate(
                subgoals,
                start=1,
            ):
                if not isinstance(
                    subgoal,
                    dict,
                ):
                    continue

                self.add_step(
                    goal_id=str(
                        subgoal.get(
                            "proposal_id",
                            subgoal.get(
                                "goal_id",
                                f"subgoal_{index}",
                            ),
                        )
                    ),
                    name=str(
                        subgoal.get(
                            "title",
                            f"Etap {index}",
                        )
                    ),
                    order=self._safe_int(
                        subgoal.get(
                            "order",
                            index,
                        ),
                        index,
                    ),
                    dependencies=self._safe_string_list(
                        subgoal.get(
                            "dependencies",
                            [],
                        )
                    ),
                    metadata={
                        "subgoal_type": subgoal.get(
                            "subgoal_type"
                        ),
                        "priority": subgoal.get(
                            "priority"
                        ),
                        "estimated_effort": (
                            subgoal.get(
                                "estimated_effort"
                            )
                        ),
                        "success_criteria": (
                            self._safe_list(
                                subgoal.get(
                                    "success_criteria",
                                    [],
                                )
                            )
                        ),
                    },
                )

        self._refresh_step_states()
        self._touch()

        return dict(self.decomposition)

    def set_graph(
        self,
        graph: dict[str, Any],
    ) -> dict[str, Any]:

        self.graph = self._safe_dict(
            graph
        )

        self.blocked_goal_ids = (
            self._safe_string_list(
                self.graph.get(
                    "blocked_goal_ids",
                    [],
                )
            )
        )

        self._refresh_step_states()
        self._touch()

        return dict(self.graph)

    def set_priority_result(
        self,
        priority_result: dict[str, Any],
    ) -> dict[str, Any]:

        self.priority_result = self._safe_dict(
            priority_result
        )

        self.next_goal_id = self._optional_string(
            self.priority_result.get(
                "next_goal_id"
            )
        )

        self._touch()
        return dict(self.priority_result)

    def set_schedule(
        self,
        schedule: dict[str, Any],
    ) -> dict[str, Any]:

        self.schedule = self._safe_dict(
            schedule
        )

        self.next_goal_id = self._optional_string(
            self.schedule.get(
                "next_goal_id",
                self.next_goal_id,
            )
        )

        self.blocked_goal_ids = (
            self._safe_string_list(
                self.schedule.get(
                    "blocked_goal_ids",
                    self.blocked_goal_ids,
                )
            )
        )

        self.status = PlanningSessionStatus.READY.value
        self._touch()

        return dict(self.schedule)

    def set_execution(
        self,
        execution: dict[str, Any],
    ) -> dict[str, Any]:

        self.execution = self._safe_dict(
            execution
        )

        execution_status = str(
            self.execution.get(
                "status",
                "",
            )
        ).upper()

        if execution_status in {
            "RUNNING",
            "ACTIVE",
        }:
            self.status = PlanningSessionStatus.RUNNING.value

        elif execution_status == "PAUSED":
            self.status = PlanningSessionStatus.PAUSED.value

        elif execution_status == "BLOCKED":
            self.status = PlanningSessionStatus.BLOCKED.value

        elif execution_status == "COMPLETED":
            self.status = PlanningSessionStatus.COMPLETED.value

        elif execution_status in {
            "FAILED",
            "ERROR",
        }:
            self.status = PlanningSessionStatus.FAILED.value

        self._collect_errors_from_dict(
            self.execution
        )

        self._touch()
        return dict(self.execution)

    def add_step(
        self,
        goal_id: str,
        name: str,
        order: int | None = None,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_order = (
            int(order)
            if order is not None
            else len(self._steps) + 1
        )

        step = PlanningStep(
            step_id=f"planning_step_{uuid4().hex}",
            goal_id=str(goal_id).strip(),
            name=str(name).strip(),
            order=max(
                1,
                normalized_order,
            ),
            status=PlanningStepStatus.PENDING.value,
            progress=0.0,
            dependencies=self._safe_string_list(
                dependencies or []
            ),
            started_at=None,
            completed_at=None,
            output={},
            errors=[],
            metadata=self._safe_dict(
                metadata
            ),
        )

        self._steps.append(step)
        self._steps.sort(
            key=lambda item: item.order
        )

        self._refresh_step_states()
        self._touch()

        return step.to_dict()

    def start(
        self,
    ) -> dict[str, Any]:

        self.status = PlanningSessionStatus.RUNNING.value
        self.started_at = self.started_at or self._utc_now()

        next_step = self.next_ready_step()

        if next_step is not None:
            self.start_step(
                next_step["step_id"]
            )

        self._touch()
        return self.to_dict()

    def pause(
        self,
        reason: str | None = None,
    ) -> dict[str, Any]:

        self.status = PlanningSessionStatus.PAUSED.value

        if reason:
            self.metadata["pause_reason"] = str(
                reason
            )

        self._touch()
        return self.to_dict()

    def resume(
        self,
    ) -> dict[str, Any]:

        self.status = PlanningSessionStatus.RUNNING.value
        self.started_at = self.started_at or self._utc_now()

        if self.current_step_id is None:
            next_step = self.next_ready_step()

            if next_step is not None:
                self.start_step(
                    next_step["step_id"]
                )

        self._touch()
        return self.to_dict()

    def start_step(
        self,
        step_id: str,
    ) -> dict[str, Any] | None:

        step = self._find_step(
            step_id
        )

        if step is None:
            return None

        if step.status not in {
            PlanningStepStatus.READY.value,
            PlanningStepStatus.PENDING.value,
            PlanningStepStatus.BLOCKED.value,
        }:
            return step.to_dict()

        if not self._step_dependencies_completed(
            step
        ):
            step.status = (
                PlanningStepStatus.BLOCKED.value
            )
            self._touch()
            return step.to_dict()

        for current in self._steps:
            if (
                current.status
                == PlanningStepStatus.RUNNING.value
            ):
                current.status = (
                    PlanningStepStatus.READY.value
                )
                current.started_at = None

        step.status = PlanningStepStatus.RUNNING.value
        step.started_at = self._utc_now()

        self.current_step_id = step.step_id

        if step.goal_id not in self.active_goal_ids:
            self.active_goal_ids.append(
                step.goal_id
            )

        self.status = PlanningSessionStatus.RUNNING.value
        self.started_at = self.started_at or self._utc_now()

        self._touch()
        return step.to_dict()

    def update_step_progress(
        self,
        step_id: str,
        progress: float,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        step = self._find_step(
            step_id
        )

        if step is None:
            return None

        step.progress = round(
            max(
                0.0,
                min(
                    1.0,
                    float(progress),
                ),
            ),
            4,
        )

        if output is not None:
            step.output.update(
                self._safe_dict(output)
            )

        if step.progress >= 1.0:
            return self.complete_step(
                step_id=step_id,
                output=step.output,
            )

        self._refresh_progress()
        self._touch()

        return step.to_dict()

    def complete_step(
        self,
        step_id: str,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        step = self._find_step(
            step_id
        )

        if step is None:
            return None

        step.status = PlanningStepStatus.COMPLETED.value
        step.progress = 1.0
        step.completed_at = self._utc_now()

        if output is not None:
            step.output = self._safe_dict(
                output
            )

        if step.goal_id not in self.completed_goal_ids:
            self.completed_goal_ids.append(
                step.goal_id
            )

        self.active_goal_ids = [
            goal_id
            for goal_id in self.active_goal_ids
            if goal_id != step.goal_id
        ]

        if self.current_step_id == step.step_id:
            self.current_step_id = None

        self._refresh_step_states()
        self._refresh_progress()

        next_step = self.next_ready_step()

        if next_step is not None:
            self.next_goal_id = next_step[
                "goal_id"
            ]

        elif self._all_required_steps_completed():
            self.complete(
                result={
                    "success": True,
                    "status": "COMPLETED",
                }
            )

        self._touch()
        return step.to_dict()

    def fail_step(
        self,
        step_id: str,
        error: str,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        step = self._find_step(
            step_id
        )

        if step is None:
            return None

        normalized_error = str(
            error
        ).strip()

        step.status = PlanningStepStatus.FAILED.value
        step.completed_at = self._utc_now()

        if output is not None:
            step.output = self._safe_dict(
                output
            )

        if normalized_error:
            step.errors = self._unique_strings(
                step.errors + [normalized_error]
            )
            self.errors = self._unique_strings(
                self.errors + [normalized_error]
            )

        self.status = PlanningSessionStatus.FAILED.value

        if self.current_step_id == step.step_id:
            self.current_step_id = None

        self.active_goal_ids = [
            goal_id
            for goal_id in self.active_goal_ids
            if goal_id != step.goal_id
        ]

        self._touch()
        return step.to_dict()

    def block_step(
        self,
        step_id: str,
        reason: str,
    ) -> dict[str, Any] | None:

        step = self._find_step(
            step_id
        )

        if step is None:
            return None

        normalized_reason = str(
            reason
        ).strip()

        step.status = PlanningStepStatus.BLOCKED.value

        if normalized_reason:
            step.errors = self._unique_strings(
                step.errors
                + [normalized_reason]
            )

        if step.goal_id not in self.blocked_goal_ids:
            self.blocked_goal_ids.append(
                step.goal_id
            )

        self.status = PlanningSessionStatus.BLOCKED.value
        self._touch()

        return step.to_dict()

    def skip_step(
        self,
        step_id: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:

        step = self._find_step(
            step_id
        )

        if step is None:
            return None

        step.status = PlanningStepStatus.SKIPPED.value
        step.completed_at = self._utc_now()

        if reason:
            step.metadata["skip_reason"] = str(
                reason
            )

        if self.current_step_id == step.step_id:
            self.current_step_id = None

        self._refresh_step_states()
        self._refresh_progress()
        self._touch()

        return step.to_dict()

    def complete(
        self,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        self.result = self._safe_dict(
            result
        )

        self.status = PlanningSessionStatus.COMPLETED.value
        self.progress = 1.0
        self.completed_at = self._utc_now()
        self.current_step_id = None

        lessons = self._safe_list(
            self.result.get(
                "lessons",
                [],
            )
        )

        self.lessons = self._unique_strings(
            self.lessons + lessons
        )

        self._touch()
        return self.to_dict()

    def fail(
        self,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_error = str(
            error
        ).strip()

        if normalized_error:
            self.errors = self._unique_strings(
                self.errors + [normalized_error]
            )

        self.result = self._safe_dict(
            result
        )

        self.status = PlanningSessionStatus.FAILED.value
        self.completed_at = self._utc_now()
        self.current_step_id = None

        self._touch()
        return self.to_dict()

    def cancel(
        self,
        reason: str | None = None,
    ) -> dict[str, Any]:

        self.status = PlanningSessionStatus.CANCELLED.value
        self.completed_at = self._utc_now()
        self.current_step_id = None

        if reason:
            self.metadata["cancel_reason"] = str(
                reason
            )

        self._touch()
        return self.to_dict()

    def add_lesson(
        self,
        lesson: str,
    ) -> list[str]:

        normalized = str(
            lesson
        ).strip()

        if normalized:
            self.lessons = self._unique_strings(
                self.lessons + [normalized]
            )

        self._touch()
        return list(self.lessons)

    def add_error(
        self,
        error: str,
    ) -> list[str]:

        normalized = str(
            error
        ).strip()

        if normalized:
            self.errors = self._unique_strings(
                self.errors + [normalized]
            )

        self._touch()
        return list(self.errors)

    def next_ready_step(
        self,
    ) -> dict[str, Any] | None:

        self._refresh_step_states()

        for step in sorted(
            self._steps,
            key=lambda item: item.order,
        ):
            if (
                step.status
                == PlanningStepStatus.READY.value
            ):
                return step.to_dict()

        return None

    def get_step(
        self,
        step_id: str,
    ) -> dict[str, Any] | None:

        step = self._find_step(
            step_id
        )

        if step is None:
            return None

        return step.to_dict()

    def get_steps(
        self,
        status: str | None = None,
    ) -> list[dict[str, Any]]:

        normalized_status = (
            str(status).upper()
            if status is not None
            else None
        )

        result: list[
            dict[str, Any]
        ] = []

        for step in sorted(
            self._steps,
            key=lambda item: item.order,
        ):
            if (
                normalized_status
                and step.status
                != normalized_status
            ):
                continue

            result.append(
                step.to_dict()
            )

        return result

    def summary(
        self,
    ) -> dict[str, Any]:

        step_counts = {
            status.value: 0
            for status in PlanningStepStatus
        }

        for step in self._steps:
            step_counts[step.status] = (
                step_counts.get(
                    step.status,
                    0,
                )
                + 1
            )

        return {
            "session_id": self.session_id,
            "root_goal_id": self.root_goal_id,
            "title": self.title,
            "status": self.status,
            "progress": round(
                self.progress,
                4,
            ),
            "steps_count": len(
                self._steps
            ),
            "step_status_counts": step_counts,
            "current_step_id": self.current_step_id,
            "next_goal_id": self.next_goal_id,
            "active_goal_ids": list(
                self.active_goal_ids
            ),
            "completed_goal_ids": list(
                self.completed_goal_ids
            ),
            "blocked_goal_ids": list(
                self.blocked_goal_ids
            ),
            "errors_count": len(
                self.errors
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

        return PlanningSessionData(
            session_id=self.session_id,
            root_goal_id=self.root_goal_id,
            title=self.title,
            status=self.status,
            progress=round(
                self.progress,
                4,
            ),
            created_at=self.created_at,
            updated_at=self.updated_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            goal=dict(self.goal),
            decomposition=dict(
                self.decomposition
            ),
            graph=dict(self.graph),
            priority_result=dict(
                self.priority_result
            ),
            schedule=dict(self.schedule),
            execution=dict(self.execution),
            result=dict(self.result),
            steps=[
                step.to_dict()
                for step in sorted(
                    self._steps,
                    key=lambda item: item.order,
                )
            ],
            current_step_id=self.current_step_id,
            next_goal_id=self.next_goal_id,
            active_goal_ids=list(
                self.active_goal_ids
            ),
            completed_goal_ids=list(
                self.completed_goal_ids
            ),
            blocked_goal_ids=list(
                self.blocked_goal_ids
            ),
            errors=list(self.errors),
            lessons=list(self.lessons),
            metadata=dict(self.metadata),
        ).to_dict()

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> PlanningSession:

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "PlanningSession.from_dict wymaga dict."
            )

        session = cls(
            root_goal_id=str(
                data.get(
                    "root_goal_id",
                    "",
                )
            ),
            title=str(
                data.get(
                    "title",
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
                PlanningSessionStatus.CREATED.value,
            )
        ).upper()

        session.progress = max(
            0.0,
            min(
                1.0,
                session._safe_float(
                    data.get(
                        "progress",
                        0.0,
                    ),
                    0.0,
                ),
            ),
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

        session.started_at = session._optional_string(
            data.get(
                "started_at"
            )
        )

        session.completed_at = session._optional_string(
            data.get(
                "completed_at"
            )
        )

        session.goal = session._safe_dict(
            data.get(
                "goal",
                {},
            )
        )

        session.decomposition = (
            session._safe_dict(
                data.get(
                    "decomposition",
                    {},
                )
            )
        )

        session.graph = session._safe_dict(
            data.get(
                "graph",
                {},
            )
        )

        session.priority_result = (
            session._safe_dict(
                data.get(
                    "priority_result",
                    {},
                )
            )
        )

        session.schedule = session._safe_dict(
            data.get(
                "schedule",
                {},
            )
        )

        session.execution = session._safe_dict(
            data.get(
                "execution",
                {},
            )
        )

        session.result = session._safe_dict(
            data.get(
                "result",
                {},
            )
        )

        session.current_step_id = (
            session._optional_string(
                data.get(
                    "current_step_id"
                )
            )
        )

        session.next_goal_id = (
            session._optional_string(
                data.get(
                    "next_goal_id"
                )
            )
        )

        session.active_goal_ids = (
            session._safe_string_list(
                data.get(
                    "active_goal_ids",
                    [],
                )
            )
        )

        session.completed_goal_ids = (
            session._safe_string_list(
                data.get(
                    "completed_goal_ids",
                    [],
                )
            )
        )

        session.blocked_goal_ids = (
            session._safe_string_list(
                data.get(
                    "blocked_goal_ids",
                    [],
                )
            )
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
            [],
        )

        if isinstance(
            raw_steps,
            list,
        ):
            for index, raw_step in enumerate(
                raw_steps,
                start=1,
            ):
                if not isinstance(
                    raw_step,
                    dict,
                ):
                    continue

                session._steps.append(
                    PlanningStep(
                        step_id=str(
                            raw_step.get(
                                "step_id",
                                f"planning_step_{uuid4().hex}",
                            )
                        ),
                        goal_id=str(
                            raw_step.get(
                                "goal_id",
                                "",
                            )
                        ),
                        name=str(
                            raw_step.get(
                                "name",
                                f"Etap {index}",
                            )
                        ),
                        order=session._safe_int(
                            raw_step.get(
                                "order",
                                index,
                            ),
                            index,
                        ),
                        status=str(
                            raw_step.get(
                                "status",
                                PlanningStepStatus.PENDING.value,
                            )
                        ).upper(),
                        progress=max(
                            0.0,
                            min(
                                1.0,
                                session._safe_float(
                                    raw_step.get(
                                        "progress",
                                        0.0,
                                    ),
                                    0.0,
                                ),
                            ),
                        ),
                        dependencies=(
                            session._safe_string_list(
                                raw_step.get(
                                    "dependencies",
                                    [],
                                )
                            )
                        ),
                        started_at=(
                            session._optional_string(
                                raw_step.get(
                                    "started_at"
                                )
                            )
                        ),
                        completed_at=(
                            session._optional_string(
                                raw_step.get(
                                    "completed_at"
                                )
                            )
                        ),
                        output=session._safe_dict(
                            raw_step.get(
                                "output",
                                {},
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
                                "metadata",
                                {},
                            )
                        ),
                    )
                )

        session._steps.sort(
            key=lambda item: item.order
        )

        return session

    def _refresh_step_states(
        self,
    ) -> None:

        for step in self._steps:
            if step.status in {
                PlanningStepStatus.COMPLETED.value,
                PlanningStepStatus.RUNNING.value,
                PlanningStepStatus.FAILED.value,
                PlanningStepStatus.SKIPPED.value,
            }:
                continue

            if self._step_dependencies_completed(
                step
            ):
                step.status = (
                    PlanningStepStatus.READY.value
                )

            else:
                step.status = (
                    PlanningStepStatus.BLOCKED.value
                )

        self.blocked_goal_ids = self._unique_strings(
            [
                step.goal_id
                for step in self._steps
                if step.status
                == PlanningStepStatus.BLOCKED.value
            ]
        )

    def _step_dependencies_completed(
        self,
        step: PlanningStep,
    ) -> bool:

        completed_step_ids = {
            current.step_id
            for current in self._steps
            if current.status
            in {
                PlanningStepStatus.COMPLETED.value,
                PlanningStepStatus.SKIPPED.value,
            }
        }

        completed_goal_ids = set(
            self.completed_goal_ids
        )

        for dependency in step.dependencies:
            if (
                dependency not in completed_step_ids
                and dependency not in completed_goal_ids
            ):
                return False

        return True

    def _all_required_steps_completed(
        self,
    ) -> bool:

        if not self._steps:
            return False

        return all(
            step.status
            in {
                PlanningStepStatus.COMPLETED.value,
                PlanningStepStatus.SKIPPED.value,
            }
            for step in self._steps
        )

    def _refresh_progress(
        self,
    ) -> None:

        if not self._steps:
            self.progress = 0.0
            return

        self.progress = round(
            sum(
                step.progress
                for step in self._steps
            ) / len(self._steps),
            4,
        )

    def _find_step(
        self,
        step_id: str,
    ) -> PlanningStep | None:

        normalized = str(
            step_id
        ).strip()

        for step in self._steps:
            if step.step_id == normalized:
                return step

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

        error = data.get(
            "error"
        )

        if error:
            errors.append(error)

        self.errors = self._unique_strings(
            self.errors + errors
        )

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

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        return self._unique_strings(
            self._safe_list(value)
        )

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

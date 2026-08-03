"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ScheduleStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ScheduleReason(str, Enum):
    PRIORITY = "PRIORITY"
    DEPENDENCY = "DEPENDENCY"
    DEADLINE = "DEADLINE"
    READINESS = "READINESS"
    MANUAL = "MANUAL"
    CONTINUATION = "CONTINUATION"


class TimeWindowType(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    TODAY = "TODAY"
    THIS_WEEK = "THIS_WEEK"
    LATER = "LATER"
    CONTINUOUS = "CONTINUOUS"


@dataclass
class ScheduledGoal:
    schedule_id: str
    goal_id: str
    title: str
    status: str
    reason: str
    priority_score: float
    order: int
    ready: bool
    blocked: bool
    dependencies: list[str]
    scheduled_for: str | None
    deadline: str | None
    estimated_effort: float
    time_window: str
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalScheduleResult:
    schedule_batch_id: str
    generated_at: str
    scheduled_goals: list[dict[str, Any]]
    ready_goal_ids: list[str]
    blocked_goal_ids: list[str]
    unscheduled_goal_ids: list[str]
    next_goal_id: str | None
    total_estimated_effort: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoalScheduler:

    TERMINAL_STATUSES = {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "ARCHIVED",
    }

    ACTIVE_STATUSES = {
        "ACTIVE",
        "RUNNING",
    }

    def __init__(
        self,
        max_parallel_goals: int = 1,
        default_daily_capacity: float = 6.0,
    ) -> None:

        self.max_parallel_goals = max(
            1,
            int(max_parallel_goals),
        )

        self.default_daily_capacity = max(
            0.5,
            float(default_daily_capacity),
        )

        self._last_result: dict[str, Any] = {}

    def schedule(
        self,
        goals: list[dict[str, Any]],
        priority_result: dict[str, Any] | None = None,
        graph_result: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_context = (
            dict(context)
            if isinstance(context, dict)
            else {}
        )

        normalized_goals = [
            self._normalize_goal(goal)
            for goal in goals
            if isinstance(goal, dict)
        ]

        goal_map = {
            goal["goal_id"]: goal
            for goal in normalized_goals
        }

        priority_map = self._build_priority_map(
            priority_result
        )

        graph_order = self._extract_graph_order(
            graph_result
        )

        ready_ids = self._resolve_ready_goal_ids(
            goals=normalized_goals,
            graph_result=graph_result,
            goal_map=goal_map,
        )

        blocked_ids = self._resolve_blocked_goal_ids(
            goals=normalized_goals,
            graph_result=graph_result,
            goal_map=goal_map,
        )

        candidate_ids = [
            goal["goal_id"]
            for goal in normalized_goals
            if goal["goal_id"] not in blocked_ids
            and goal["status"] not in self.TERMINAL_STATUSES
        ]

        ordered_ids = self._order_candidates(
            candidate_ids=candidate_ids,
            goal_map=goal_map,
            priority_map=priority_map,
            graph_order=graph_order,
            ready_ids=ready_ids,
        )

        scheduled_goals = self._assign_schedule(
            ordered_ids=ordered_ids,
            goal_map=goal_map,
            priority_map=priority_map,
            ready_ids=ready_ids,
            blocked_ids=blocked_ids,
            context=normalized_context,
        )

        scheduled_goal_ids = {
            item.goal_id
            for item in scheduled_goals
        }

        unscheduled_goal_ids = [
            goal["goal_id"]
            for goal in normalized_goals
            if (
                goal["goal_id"]
                not in scheduled_goal_ids
                and goal["status"]
                not in self.TERMINAL_STATUSES
            )
        ]

        next_goal_id = self._select_next_goal(
            scheduled_goals
        )

        result = GoalScheduleResult(
            schedule_batch_id=(
                f"goal_schedule_{uuid4().hex}"
            ),
            generated_at=self._utc_now(),
            scheduled_goals=[
                item.to_dict()
                for item in scheduled_goals
            ],
            ready_goal_ids=[
                goal_id
                for goal_id in ordered_ids
                if goal_id in ready_ids
            ],
            blocked_goal_ids=self._sort_ids(
                blocked_ids,
                goal_map,
                priority_map,
            ),
            unscheduled_goal_ids=unscheduled_goal_ids,
            next_goal_id=next_goal_id,
            total_estimated_effort=round(
                sum(
                    item.estimated_effort
                    for item in scheduled_goals
                ),
                2,
            ),
            metadata={
                "scheduler_version": "1.0.0",
                "goals_count": len(
                    normalized_goals
                ),
                "scheduled_count": len(
                    scheduled_goals
                ),
                "ready_count": len(
                    ready_ids
                ),
                "blocked_count": len(
                    blocked_ids
                ),
                "max_parallel_goals": (
                    self.max_parallel_goals
                ),
                "daily_capacity": (
                    self._safe_float(
                        normalized_context.get(
                            "daily_capacity",
                            self.default_daily_capacity,
                        ),
                        self.default_daily_capacity,
                    )
                ),
            },
        )

        self._last_result = result.to_dict()
        return dict(self._last_result)

    def build(
        self,
        goals: list[dict[str, Any]],
        priority_result: dict[str, Any] | None = None,
        graph_result: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.schedule(
            goals=goals,
            priority_result=priority_result,
            graph_result=graph_result,
            context=context,
        )

    def generate(
        self,
        goals: list[dict[str, Any]],
        priority_result: dict[str, Any] | None = None,
        graph_result: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.schedule(
            goals=goals,
            priority_result=priority_result,
            graph_result=graph_result,
            context=context,
        )

    def get_next_goal(
        self,
    ) -> dict[str, Any] | None:

        scheduled_goals = self._last_result.get(
            "scheduled_goals",
            [],
        )

        if not isinstance(
            scheduled_goals,
            list,
        ):
            return None

        for item in scheduled_goals:
            if not isinstance(
                item,
                dict,
            ):
                continue

            if (
                item.get("ready") is True
                and item.get("blocked") is False
                and item.get("status")
                in {
                    ScheduleStatus.READY.value,
                    ScheduleStatus.SCHEDULED.value,
                    ScheduleStatus.RUNNING.value,
                }
            ):
                return dict(item)

        return None

    def get_schedule(
        self,
    ) -> dict[str, Any]:

        return dict(self._last_result)

    def reschedule(
        self,
        goals: list[dict[str, Any]],
        priority_result: dict[str, Any] | None = None,
        graph_result: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.schedule(
            goals=goals,
            priority_result=priority_result,
            graph_result=graph_result,
            context=context,
        )

    def _assign_schedule(
        self,
        ordered_ids: list[str],
        goal_map: dict[str, dict[str, Any]],
        priority_map: dict[str, dict[str, Any]],
        ready_ids: set[str],
        blocked_ids: set[str],
        context: dict[str, Any],
    ) -> list[ScheduledGoal]:

        now = datetime.now(
            timezone.utc
        )

        daily_capacity = max(
            0.5,
            self._safe_float(
                context.get(
                    "daily_capacity",
                    self.default_daily_capacity,
                ),
                self.default_daily_capacity,
            ),
        )

        capacity_left = daily_capacity
        day_offset = 0

        scheduled: list[ScheduledGoal] = []

        for order, goal_id in enumerate(
            ordered_ids,
            start=1,
        ):
            goal = goal_map[goal_id]

            priority_data = priority_map.get(
                goal_id,
                {},
            )

            priority_score = self._safe_float(
                priority_data.get(
                    "priority_score",
                    self._fallback_priority_score(
                        goal["priority"]
                    ),
                ),
                0.0,
            )

            blocked = (
                goal_id in blocked_ids
                or bool(goal["blockers"])
            )

            ready = (
                goal_id in ready_ids
                and not blocked
            )

            effort = self._normalize_effort(
                goal.get(
                    "estimated_effort"
                )
            )

            scheduled_for: str | None = None
            status = ScheduleStatus.PENDING.value
            reason = ScheduleReason.PRIORITY.value
            notes: list[str] = []

            if blocked:
                status = ScheduleStatus.BLOCKED.value
                reason = ScheduleReason.DEPENDENCY.value
                notes.append(
                    "Cel jest zablokowany przez zależności "
                    "lub aktywne blokery."
                )

            elif ready:
                if (
                    goal["status"]
                    in self.ACTIVE_STATUSES
                ):
                    status = (
                        ScheduleStatus.RUNNING.value
                    )
                    reason = (
                        ScheduleReason.CONTINUATION.value
                    )
                    scheduled_for = now.isoformat()

                else:
                    status = (
                        ScheduleStatus.READY.value
                    )

                    if effort > capacity_left:
                        day_offset += 1
                        capacity_left = daily_capacity

                    scheduled_for = (
                        now
                        + timedelta(
                            days=day_offset
                        )
                    ).isoformat()

                    capacity_left = max(
                        0.0,
                        capacity_left - effort,
                    )

                    reason = self._choose_reason(
                        goal=goal,
                        priority_score=priority_score,
                    )

            else:
                status = ScheduleStatus.PENDING.value
                reason = ScheduleReason.DEPENDENCY.value
                notes.append(
                    "Cel oczekuje na zakończenie zależności."
                )

            time_window = self._time_window(
                scheduled_for=scheduled_for,
                goal=goal,
                now=now,
            )

            scheduled.append(
                ScheduledGoal(
                    schedule_id=(
                        f"scheduled_goal_"
                        f"{uuid4().hex}"
                    ),
                    goal_id=goal_id,
                    title=goal["title"],
                    status=status,
                    reason=reason,
                    priority_score=round(
                        priority_score,
                        2,
                    ),
                    order=order,
                    ready=ready,
                    blocked=blocked,
                    dependencies=list(
                        goal["dependencies"]
                    ),
                    scheduled_for=scheduled_for,
                    deadline=goal["deadline"],
                    estimated_effort=effort,
                    time_window=time_window,
                    notes=notes,
                    metadata={
                        "goal_status": goal[
                            "status"
                        ],
                        "goal_priority": goal[
                            "priority"
                        ],
                        "goal_timeframe": goal[
                            "timeframe"
                        ],
                    },
                )
            )

        return scheduled

    def _order_candidates(
        self,
        candidate_ids: list[str],
        goal_map: dict[str, dict[str, Any]],
        priority_map: dict[str, dict[str, Any]],
        graph_order: list[str],
        ready_ids: set[str],
    ) -> list[str]:

        graph_index = {
            goal_id: index
            for index, goal_id
            in enumerate(graph_order)
        }

        def sort_key(
            goal_id: str,
        ) -> tuple[int, float, int, str]:

            goal = goal_map[goal_id]

            ready_rank = (
                0
                if goal_id in ready_ids
                else 1
            )

            priority_score = self._safe_float(
                priority_map.get(
                    goal_id,
                    {},
                ).get(
                    "priority_score",
                    self._fallback_priority_score(
                        goal["priority"]
                    ),
                ),
                0.0,
            )

            graph_rank = graph_index.get(
                goal_id,
                999999,
            )

            return (
                ready_rank,
                -priority_score,
                graph_rank,
                goal["title"].lower(),
            )

        return sorted(
            candidate_ids,
            key=sort_key,
        )

    def _resolve_ready_goal_ids(
        self,
        goals: list[dict[str, Any]],
        graph_result: dict[str, Any] | None,
        goal_map: dict[str, dict[str, Any]],
    ) -> set[str]:

        if isinstance(
            graph_result,
            dict,
        ):
            raw_ready = graph_result.get(
                "ready_goal_ids"
            )

            if isinstance(
                raw_ready,
                list,
            ):
                return {
                    str(goal_id)
                    for goal_id in raw_ready
                    if str(goal_id) in goal_map
                }

        ready: set[str] = set()

        for goal in goals:
            if self._goal_is_ready(
                goal,
                goal_map,
            ):
                ready.add(
                    goal["goal_id"]
                )

        return ready

    def _resolve_blocked_goal_ids(
        self,
        goals: list[dict[str, Any]],
        graph_result: dict[str, Any] | None,
        goal_map: dict[str, dict[str, Any]],
    ) -> set[str]:

        if isinstance(
            graph_result,
            dict,
        ):
            raw_blocked = graph_result.get(
                "blocked_goal_ids"
            )

            if isinstance(
                raw_blocked,
                list,
            ):
                return {
                    str(goal_id)
                    for goal_id in raw_blocked
                    if str(goal_id) in goal_map
                }

        blocked: set[str] = set()

        for goal in goals:
            if (
                goal["blockers"]
                or not self._dependencies_completed(
                    goal,
                    goal_map,
                )
            ):
                blocked.add(
                    goal["goal_id"]
                )

        return blocked

    def _build_priority_map(
        self,
        priority_result: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:

        if not isinstance(
            priority_result,
            dict,
        ):
            return {}

        assessments = priority_result.get(
            "assessments",
            [],
        )

        if not isinstance(
            assessments,
            list,
        ):
            return {}

        result: dict[
            str,
            dict[str, Any],
        ] = {}

        for item in assessments:
            if not isinstance(
                item,
                dict,
            ):
                continue

            goal_id = str(
                item.get(
                    "goal_id",
                    "",
                )
            ).strip()

            if goal_id:
                result[goal_id] = dict(item)

        return result

    def _extract_graph_order(
        self,
        graph_result: dict[str, Any] | None,
    ) -> list[str]:

        if not isinstance(
            graph_result,
            dict,
        ):
            return []

        order = graph_result.get(
            "execution_order",
            [],
        )

        if not isinstance(
            order,
            list,
        ):
            return []

        return [
            str(goal_id)
            for goal_id in order
            if str(goal_id).strip()
        ]

    def _select_next_goal(
        self,
        scheduled_goals: list[ScheduledGoal],
    ) -> str | None:

        for item in scheduled_goals:
            if (
                item.ready
                and not item.blocked
                and item.status
                in {
                    ScheduleStatus.READY.value,
                    ScheduleStatus.RUNNING.value,
                    ScheduleStatus.SCHEDULED.value,
                }
            ):
                return item.goal_id

        return None

    def _goal_is_ready(
        self,
        goal: dict[str, Any],
        goal_map: dict[str, dict[str, Any]],
    ) -> bool:

        if goal["status"] in self.TERMINAL_STATUSES:
            return False

        if goal["blockers"]:
            return False

        return self._dependencies_completed(
            goal,
            goal_map,
        )

    def _dependencies_completed(
        self,
        goal: dict[str, Any],
        goal_map: dict[str, dict[str, Any]],
    ) -> bool:

        for dependency_id in goal[
            "dependencies"
        ]:
            dependency = goal_map.get(
                dependency_id
            )

            if dependency is None:
                return False

            if dependency["status"] != "COMPLETED":
                return False

        return True

    def _choose_reason(
        self,
        goal: dict[str, Any],
        priority_score: float,
    ) -> str:

        if goal["deadline"]:
            deadline_score = self._deadline_urgency(
                goal["deadline"]
            )

            if deadline_score >= 15.0:
                return ScheduleReason.DEADLINE.value

        if (
            goal["status"]
            in self.ACTIVE_STATUSES
        ):
            return ScheduleReason.CONTINUATION.value

        if priority_score >= 65.0:
            return ScheduleReason.PRIORITY.value

        return ScheduleReason.READINESS.value

    def _time_window(
        self,
        scheduled_for: str | None,
        goal: dict[str, Any],
        now: datetime,
    ) -> str:

        if goal["timeframe"] == "CONTINUOUS":
            return TimeWindowType.CONTINUOUS.value

        if scheduled_for is None:
            return TimeWindowType.LATER.value

        try:
            scheduled_dt = datetime.fromisoformat(
                scheduled_for.replace(
                    "Z",
                    "+00:00",
                )
            )

            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(
                    tzinfo=timezone.utc
                )

            delta_days = (
                scheduled_dt.date()
                - now.date()
            ).days

            if delta_days <= 0:
                if goal["priority"] == "CRITICAL":
                    return TimeWindowType.IMMEDIATE.value

                return TimeWindowType.TODAY.value

            if delta_days <= 7:
                return TimeWindowType.THIS_WEEK.value

            return TimeWindowType.LATER.value

        except (
            TypeError,
            ValueError,
        ):
            return TimeWindowType.LATER.value

    def _deadline_urgency(
        self,
        deadline: str | None,
    ) -> float:

        if deadline is None:
            return 0.0

        try:
            deadline_dt = datetime.fromisoformat(
                str(deadline).replace(
                    "Z",
                    "+00:00",
                )
            )

            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(
                    tzinfo=timezone.utc
                )

            now = datetime.now(
                timezone.utc
            )

            days_left = (
                deadline_dt - now
            ).total_seconds() / 86400.0

            if days_left < 0:
                return 25.0

            if days_left <= 1:
                return 22.0

            if days_left <= 3:
                return 18.0

            if days_left <= 7:
                return 15.0

            if days_left <= 30:
                return 8.0

            return 2.0

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    def _sort_ids(
        self,
        goal_ids: set[str],
        goal_map: dict[str, dict[str, Any]],
        priority_map: dict[str, dict[str, Any]],
    ) -> list[str]:

        return sorted(
            [
                goal_id
                for goal_id in goal_ids
                if goal_id in goal_map
            ],
            key=lambda goal_id: (
                -self._safe_float(
                    priority_map.get(
                        goal_id,
                        {},
                    ).get(
                        "priority_score",
                        self._fallback_priority_score(
                            goal_map[
                                goal_id
                            ]["priority"]
                        ),
                    ),
                    0.0,
                ),
                goal_map[
                    goal_id
                ]["title"].lower(),
            ),
        )

    def _fallback_priority_score(
        self,
        priority: str,
    ) -> float:

        return {
            "LOW": 20.0,
            "MEDIUM": 45.0,
            "HIGH": 70.0,
            "CRITICAL": 90.0,
        }.get(
            str(priority).upper(),
            45.0,
        )

    def _normalize_effort(
        self,
        value: Any,
    ) -> float:

        effort = self._safe_float(
            value,
            1.0,
        )

        if effort <= 0:
            return 1.0

        return round(
            effort,
            2,
        )

    def _normalize_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        goal_id = str(
            goal.get(
                "goal_id",
                f"goal_{uuid4().hex}",
            )
        ).strip()

        return {
            "goal_id": goal_id,
            "title": str(
                goal.get(
                    "title",
                    goal_id,
                )
            ).strip(),
            "status": str(
                goal.get(
                    "status",
                    "CREATED",
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
            "dependencies": self._safe_list(
                goal.get(
                    "dependencies",
                    [],
                )
            ),
            "blockers": self._safe_list(
                goal.get(
                    "blockers",
                    [],
                )
            ),
            "deadline": self._optional_string(
                goal.get(
                    "deadline"
                )
            ),
            "estimated_effort": (
                goal.get(
                    "estimated_effort"
                )
            ),
        }

    def _safe_list(
        self,
        value: Any,
    ) -> list[str]:

        if not isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            return []

        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(value).strip()

        return normalized or None

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

    def _utc_now(
        self,
    ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

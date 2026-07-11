from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class PriorityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PriorityReason(str, Enum):
    BASE_PRIORITY = "BASE_PRIORITY"
    DEADLINE = "DEADLINE"
    BLOCKER = "BLOCKER"
    DEPENDENCY = "DEPENDENCY"
    READINESS = "READINESS"
    PROGRESS = "PROGRESS"
    RISK = "RISK"
    EFFORT = "EFFORT"
    TIMEFRAME = "TIMEFRAME"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


@dataclass
class PriorityFactor:
    factor_id: str
    reason: str
    description: str
    value: float
    weight: float
    weighted_value: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoalPriorityAssessment:
    assessment_id: str
    goal_id: str
    title: str
    original_priority: str
    calculated_priority: str
    priority_score: float
    ready: bool
    blocked: bool
    factors: list[dict[str, Any]]
    recommendation: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriorityEvaluationResult:
    evaluation_id: str
    assessments: list[dict[str, Any]]
    ordered_goal_ids: list[str]
    next_goal_id: str | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PriorityManager:

    BASE_PRIORITY_SCORES = {
        PriorityLevel.LOW.value: 20.0,
        PriorityLevel.MEDIUM.value: 45.0,
        PriorityLevel.HIGH.value: 70.0,
        PriorityLevel.CRITICAL.value: 90.0,
    }

    TIMEFRAME_BONUS = {
        "SHORT_TERM": 12.0,
        "MEDIUM_TERM": 6.0,
        "LONG_TERM": 2.0,
        "CONTINUOUS": 4.0,
    }

    def evaluate(
        self,
        goals: list[dict[str, Any]],
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

        assessments = [
            self._assess_goal(
                goal=goal,
                goal_map=goal_map,
                context=normalized_context,
            )
            for goal in normalized_goals
        ]

        ordered = sorted(
            assessments,
            key=lambda item: (
                -item.priority_score,
                item.blocked,
                item.title.lower(),
            ),
        )

        next_goal_id = None

        for assessment in ordered:
            if (
                assessment.ready
                and not assessment.blocked
            ):
                next_goal_id = assessment.goal_id
                break

        result = PriorityEvaluationResult(
            evaluation_id=f"priority_evaluation_{uuid4().hex}",
            assessments=[
                item.to_dict()
                for item in ordered
            ],
            ordered_goal_ids=[
                item.goal_id
                for item in ordered
            ],
            next_goal_id=next_goal_id,
            metadata={
                "priority_manager_version": "1.0.0",
                "goals_count": len(ordered),
                "ready_count": sum(
                    1
                    for item in ordered
                    if item.ready
                ),
                "blocked_count": sum(
                    1
                    for item in ordered
                    if item.blocked
                ),
            },
        )

        return result.to_dict()

    def rank(
        self,
        goals: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.evaluate(
            goals=goals,
            context=context,
        )

    def choose_next(
        self,
        goals: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        result = self.evaluate(
            goals=goals,
            context=context,
        )

        next_goal_id = result.get(
            "next_goal_id"
        )

        if not next_goal_id:
            return None

        for assessment in result.get(
            "assessments",
            [],
        ):
            if assessment.get(
                "goal_id"
            ) == next_goal_id:
                return assessment

        return None

    def _assess_goal(
        self,
        goal: dict[str, Any],
        goal_map: dict[str, dict[str, Any]],
        context: dict[str, Any],
    ) -> GoalPriorityAssessment:

        factors: list[PriorityFactor] = []

        base_score = self.BASE_PRIORITY_SCORES.get(
            goal["priority"],
            45.0,
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.BASE_PRIORITY,
                description=(
                    "Bazowy priorytet celu."
                ),
                value=base_score,
                weight=1.0,
            )
        )

        deadline_score = self._deadline_score(
            goal.get("deadline")
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.DEADLINE,
                description=(
                    "Wpływ terminu końcowego."
                ),
                value=deadline_score,
                weight=1.0,
            )
        )

        blocked = bool(
            goal.get("blockers")
        )

        blocker_score = (
            -40.0
            if blocked
            else 0.0
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.BLOCKER,
                description=(
                    "Wpływ aktywnych blokerów."
                ),
                value=blocker_score,
                weight=1.0,
            )
        )

        dependencies_completed = (
            self._dependencies_completed(
                goal,
                goal_map,
            )
        )

        dependency_score = (
            10.0
            if dependencies_completed
            else -25.0
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.DEPENDENCY,
                description=(
                    "Wpływ zależności celu."
                ),
                value=dependency_score,
                weight=1.0,
            )
        )

        ready = (
            not blocked
            and dependencies_completed
            and goal["status"]
            not in {
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                "ARCHIVED",
            }
        )

        readiness_score = (
            12.0
            if ready
            else -8.0
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.READINESS,
                description=(
                    "Gotowość celu do wykonania."
                ),
                value=readiness_score,
                weight=1.0,
            )
        )

        progress = goal["progress"]

        progress_score = 0.0

        if 0.0 < progress < 1.0:
            progress_score = 8.0

        elif progress >= 1.0:
            progress_score = -100.0

        factors.append(
            self._make_factor(
                reason=PriorityReason.PROGRESS,
                description=(
                    "Wpływ obecnego postępu."
                ),
                value=progress_score,
                weight=1.0,
            )
        )

        risk_score = self._risk_score(
            goal,
            context,
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.RISK,
                description=(
                    "Wpływ ryzyka na kolejność wykonania."
                ),
                value=risk_score,
                weight=1.0,
            )
        )

        effort_score = self._effort_score(
            goal.get(
                "estimated_effort"
            )
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.EFFORT,
                description=(
                    "Wpływ szacowanego wysiłku."
                ),
                value=effort_score,
                weight=1.0,
            )
        )

        timeframe_score = self.TIMEFRAME_BONUS.get(
            goal["timeframe"],
            0.0,
        )

        factors.append(
            self._make_factor(
                reason=PriorityReason.TIMEFRAME,
                description=(
                    "Wpływ horyzontu czasowego."
                ),
                value=timeframe_score,
                weight=1.0,
            )
        )

        manual_overrides = context.get(
            "priority_overrides",
            {}
        )

        manual_score = 0.0

        if isinstance(
            manual_overrides,
            dict,
        ):
            manual_score = self._safe_float(
                manual_overrides.get(
                    goal["goal_id"],
                    0.0,
                ),
                0.0,
            )

        factors.append(
            self._make_factor(
                reason=PriorityReason.MANUAL_OVERRIDE,
                description=(
                    "Ręczna korekta priorytetu."
                ),
                value=manual_score,
                weight=1.0,
            )
        )

        score = sum(
            factor.weighted_value
            for factor in factors
        )

        score = round(
            max(
                0.0,
                min(
                    100.0,
                    score,
                ),
            ),
            2,
        )

        calculated_priority = (
            self._priority_from_score(
                score
            )
        )

        recommendation = (
            self._build_recommendation(
                goal=goal,
                score=score,
                ready=ready,
                blocked=blocked,
                dependencies_completed=(
                    dependencies_completed
                ),
            )
        )

        return GoalPriorityAssessment(
            assessment_id=f"priority_assessment_{uuid4().hex}",
            goal_id=goal["goal_id"],
            title=goal["title"],
            original_priority=goal["priority"],
            calculated_priority=(
                calculated_priority
            ),
            priority_score=score,
            ready=ready,
            blocked=blocked,
            factors=[
                factor.to_dict()
                for factor in factors
            ],
            recommendation=recommendation,
            metadata={
                "status": goal["status"],
                "timeframe": goal["timeframe"],
                "progress": goal["progress"],
                "deadline": goal["deadline"],
            },
        )

    def _deadline_score(
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
                return 14.0

            if days_left <= 30:
                return 8.0

            return 2.0

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    def _dependencies_completed(
        self,
        goal: dict[str, Any],
        goal_map: dict[str, dict[str, Any]],
    ) -> bool:

        for dependency_id in goal.get(
            "dependencies",
            [],
        ):
            dependency = goal_map.get(
                dependency_id
            )

            if dependency is None:
                return False

            if dependency.get(
                "status"
            ) != "COMPLETED":
                return False

        return True

    def _risk_score(
        self,
        goal: dict[str, Any],
        context: dict[str, Any],
    ) -> float:

        risk_map = context.get(
            "risk_by_goal",
            {}
        )

        if not isinstance(
            risk_map,
            dict,
        ):
            return 0.0

        risk_value = risk_map.get(
            goal["goal_id"]
        )

        if risk_value is None:
            return 0.0

        if isinstance(
            risk_value,
            str,
        ):
            mapping = {
                "VERY_LOW": 5.0,
                "LOW": 2.0,
                "MEDIUM": -4.0,
                "HIGH": -12.0,
                "CRITICAL": -25.0,
            }

            return mapping.get(
                risk_value.upper(),
                0.0,
            )

        numeric = self._safe_float(
            risk_value,
            0.0,
        )

        return -min(
            25.0,
            max(
                0.0,
                numeric,
            ) * 0.25,
        )

    def _effort_score(
        self,
        effort: Any,
    ) -> float:

        numeric_effort = self._safe_float(
            effort,
            0.0,
        )

        if numeric_effort <= 0:
            return 0.0

        if numeric_effort <= 1:
            return 8.0

        if numeric_effort <= 3:
            return 5.0

        if numeric_effort <= 6:
            return 2.0

        if numeric_effort <= 12:
            return -3.0

        return -8.0

    def _priority_from_score(
        self,
        score: float,
    ) -> str:

        if score >= 85.0:
            return PriorityLevel.CRITICAL.value

        if score >= 65.0:
            return PriorityLevel.HIGH.value

        if score >= 35.0:
            return PriorityLevel.MEDIUM.value

        return PriorityLevel.LOW.value

    def _build_recommendation(
        self,
        goal: dict[str, Any],
        score: float,
        ready: bool,
        blocked: bool,
        dependencies_completed: bool,
    ) -> str:

        if goal["status"] == "COMPLETED":
            return (
                "Cel jest zakończony i nie wymaga wykonania."
            )

        if blocked:
            return (
                "Najpierw usuń aktywne blokery celu."
            )

        if not dependencies_completed:
            return (
                "Najpierw wykonaj brakujące zależności."
            )

        if ready and score >= 65.0:
            return (
                "Cel powinien zostać wykonany jako jeden z pierwszych."
            )

        if ready:
            return (
                "Cel jest gotowy do wykonania."
            )

        return (
            "Cel wymaga dalszego przygotowania."
        )

    def _make_factor(
        self,
        reason: PriorityReason,
        description: str,
        value: float,
        weight: float,
    ) -> PriorityFactor:

        return PriorityFactor(
            factor_id=f"priority_factor_{uuid4().hex}",
            reason=reason.value,
            description=description,
            value=round(
                float(value),
                2,
            ),
            weight=round(
                float(weight),
                2,
            ),
            weighted_value=round(
                float(value)
                * float(weight),
                2,
            ),
            metadata={
                "priority_manager_version": "1.0.0",
            },
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
            "priority": str(
                goal.get(
                    "priority",
                    PriorityLevel.MEDIUM.value,
                )
            ).upper(),
            "timeframe": str(
                goal.get(
                    "timeframe",
                    "MEDIUM_TERM",
                )
            ).upper(),
            "status": str(
                goal.get(
                    "status",
                    "CREATED",
                )
            ).upper(),
            "progress": max(
                0.0,
                min(
                    1.0,
                    self._safe_float(
                        goal.get(
                            "progress",
                            0.0,
                        ),
                        0.0,
                    ),
                ),
            ),
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

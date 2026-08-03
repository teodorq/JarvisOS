from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import ImplementationPlan, ImplementationTask


@dataclass(frozen=True)
class TaskSelection:
    task_id: str
    title: str
    score: float
    reason: str
    blocking_power: int
    estimated_roi: float
    estimated_risk: float
    priority: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "score": self.score,
            "reason": self.reason,
            "blocking_power": self.blocking_power,
            "estimated_roi": self.estimated_roi,
            "estimated_risk": self.estimated_risk,
            "priority": self.priority,
        }


class ImplementationPlanner:
    """Selects the best ready implementation task.

    The planner never selects tasks whose dependencies are incomplete.
    Ready tasks are ranked by ROI, risk, priority and how many later
    tasks they unblock.
    """

    PRIORITY_WEIGHT = {
        "critical": 1.00,
        "high": 0.80,
        "normal": 0.55,
        "medium": 0.55,
        "low": 0.25,
    }

    def select_next(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
    ) -> TaskSelection | None:
        selections = self.rank_ready_tasks(
            plan,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
            limit=1,
        )

        return selections[0] if selections else None

    def rank_ready_tasks(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> list[TaskSelection]:
        completed = set(completed_task_ids or ())
        failed = set(failed_task_ids or ())
        task_map = {
            task.task_id: task
            for task in plan.tasks
        }

        unknown_completed = completed - set(task_map)
        unknown_failed = failed - set(task_map)

        if unknown_completed or unknown_failed:
            unknown = sorted(
                unknown_completed | unknown_failed
            )
            raise ValueError(
                f"Unknown task identifiers: {unknown}"
            )

        ready = [
            task
            for task in plan.tasks
            if task.task_id not in completed
            and task.task_id not in failed
            and set(task.dependencies).issubset(completed)
        ]

        blocking_power = self._blocking_power(
            plan.tasks
        )
        ranked = [
            self._selection(
                task=task,
                blocking_power=blocking_power.get(
                    task.task_id,
                    0,
                ),
            )
            for task in ready
        ]

        ranked.sort(
            key=lambda item: (
                -item.score,
                -item.blocking_power,
                item.estimated_risk,
                item.task_id,
            )
        )

        if limit is None:
            return ranked

        return ranked[:max(0, int(limit))]

    def blocked_tasks(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        completed = set(completed_task_ids or ())
        failed = set(failed_task_ids or ())
        blocked: list[dict[str, Any]] = []

        for task in plan.tasks:
            if task.task_id in completed:
                continue

            missing = [
                dependency
                for dependency in task.dependencies
                if dependency not in completed
            ]

            failed_dependencies = [
                dependency
                for dependency in missing
                if dependency in failed
            ]

            if missing:
                blocked.append(
                    {
                        "task_id": task.task_id,
                        "title": task.title,
                        "missing_dependencies": missing,
                        "failed_dependencies": (
                            failed_dependencies
                        ),
                        "hard_blocked": bool(
                            failed_dependencies
                        ),
                    }
                )

        return blocked

    def plan_iteration(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        max_tasks: int = 3,
    ) -> dict[str, Any]:
        selected = self.rank_ready_tasks(
            plan,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
            limit=max_tasks,
        )

        return {
            "objective": plan.objective,
            "status": (
                "READY"
                if selected
                else "NO_READY_TASKS"
            ),
            "selected_tasks": [
                item.to_dict()
                for item in selected
            ],
            "blocked_tasks": self.blocked_tasks(
                plan,
                completed_task_ids=completed_task_ids,
                failed_task_ids=failed_task_ids,
            ),
        }

    def _selection(
        self,
        *,
        task: ImplementationTask,
        blocking_power: int,
    ) -> TaskSelection:
        priority_weight = self.PRIORITY_WEIGHT.get(
            task.priority.lower(),
            0.50,
        )

        roi = self._clamp(
            task.estimated_roi
        )
        risk = self._clamp(
            task.estimated_risk
        )
        unblock_bonus = min(
            blocking_power / 10.0,
            1.0,
        )

        score = (
            roi * 0.45
            + (1.0 - risk) * 0.25
            + priority_weight * 0.20
            + unblock_bonus * 0.10
        )

        reason = (
            f"ROI={roi:.2f}, "
            f"risk={risk:.2f}, "
            f"priority={task.priority}, "
            f"unblocks={blocking_power}"
        )

        return TaskSelection(
            task_id=task.task_id,
            title=task.title,
            score=round(score, 4),
            reason=reason,
            blocking_power=blocking_power,
            estimated_roi=roi,
            estimated_risk=risk,
            priority=task.priority,
        )

    @staticmethod
    def _blocking_power(
        tasks: list[ImplementationTask],
    ) -> dict[str, int]:
        direct_children: dict[str, set[str]] = {
            task.task_id: set()
            for task in tasks
        }

        for task in tasks:
            for dependency in task.dependencies:
                direct_children.setdefault(
                    dependency,
                    set(),
                ).add(task.task_id)

        result: dict[str, int] = {}

        for task_id in direct_children:
            visited: set[str] = set()
            stack = list(
                direct_children.get(
                    task_id,
                    set(),
                )
            )

            while stack:
                child = stack.pop()

                if child in visited:
                    continue

                visited.add(child)
                stack.extend(
                    direct_children.get(
                        child,
                        set(),
                    )
                )

            result[task_id] = len(visited)

        return result

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:
        return max(
            0.0,
            min(1.0, float(value)),
        )

from __future__ import annotations

from typing import Any, Iterable

from .blocking_task_detector import BlockingTaskDetector
from .implementation_planner import ImplementationPlanner
from .models import ImplementationPlan


class IterationPlanner:

    def __init__(
        self,
        *,
        implementation_planner: ImplementationPlanner | None = None,
        blocking_detector: BlockingTaskDetector | None = None,
    ) -> None:
        self.implementation_planner = (
            implementation_planner
            or ImplementationPlanner()
        )
        self.blocking_detector = (
            blocking_detector
            or BlockingTaskDetector()
        )

    def build_iteration(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        max_tasks: int = 3,
        max_estimated_minutes: int = 120,
    ) -> dict[str, Any]:
        completed = set(completed_task_ids or ())
        failed = set(failed_task_ids or ())

        ranked = self.implementation_planner.rank_ready_tasks(
            plan,
            completed_task_ids=completed,
            failed_task_ids=failed,
        )
        task_map = {
            task.task_id: task
            for task in plan.tasks
        }

        selected: list[dict[str, Any]] = []
        used_minutes = 0

        for candidate in ranked:
            if len(selected) >= max(1, int(max_tasks)):
                break

            task = task_map[candidate.task_id]
            task_minutes = int(task.estimated_minutes)

            if (
                selected
                and used_minutes + task_minutes
                > max_estimated_minutes
            ):
                continue

            used_minutes += task_minutes
            item = candidate.to_dict()
            item["estimated_minutes"] = task_minutes
            item["category"] = task.category
            item["acceptance_criteria"] = list(
                task.acceptance_criteria
            )
            selected.append(item)

        blocking_report = self.blocking_detector.analyze(
            plan,
            completed_task_ids=completed,
            failed_task_ids=failed,
        )

        remaining = [
            task.task_id
            for task in plan.tasks
            if task.task_id not in completed
            and task.task_id not in failed
        ]

        if not remaining:
            status = "COMPLETED"
        elif selected:
            status = "READY"
        elif blocking_report["hard_blocked_count"]:
            status = "HARD_BLOCKED"
        else:
            status = "WAITING"

        return {
            "objective": plan.objective,
            "status": status,
            "iteration": {
                "selected_tasks": selected,
                "task_count": len(selected),
                "estimated_minutes": used_minutes,
                "max_tasks": max_tasks,
                "max_estimated_minutes": max_estimated_minutes,
            },
            "blocking_report": blocking_report,
            "progress": {
                "completed": len(completed),
                "failed": len(failed),
                "remaining": len(remaining),
                "total": len(plan.tasks),
            },
        }

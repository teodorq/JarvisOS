from __future__ import annotations

from typing import Any, Iterable

from .implementation_graph import ImplementationGraph
from .implementation_scheduler import (
    ImplementationScheduler,
)
from .models import ImplementationPlan
from .task_decomposition_engine import (
    TaskDecompositionEngine,
)


class DecompositionController:

    def __init__(
        self,
        task_queue: object | None = None,
    ) -> None:
        self.task_queue = task_queue
        self.engine = TaskDecompositionEngine()
        self.scheduler = ImplementationScheduler(
            task_queue=task_queue,
        )

    def create_plan(
        self,
        objective: str,
        *,
        enqueue: bool = False,
    ) -> dict[str, Any]:
        plan = self.engine.decompose(
            objective
        )
        result = {
            "success": True,
            "status": "PLANNED",
            "plan": plan.to_dict(),
            "graph": ImplementationGraph.build(
                plan
            ),
        }

        if enqueue:
            result["queue"] = self.enqueue_plan(
                plan
            )

        return result

    def create_and_schedule(
        self,
        objective: str,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        mode: str = "iteration",
        max_tasks: int = 3,
        max_estimated_minutes: int = 120,
        enqueue: bool = True,
    ) -> dict[str, Any]:
        plan = self.engine.decompose(
            objective
        )

        scheduling = self.schedule_plan(
            plan,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
            mode=mode,
            max_tasks=max_tasks,
            max_estimated_minutes=(
                max_estimated_minutes
            ),
            enqueue=enqueue,
        )

        return {
            "success": True,
            "status": "PLANNED_AND_SCHEDULED",
            "plan": plan.to_dict(),
            "graph": ImplementationGraph.build(
                plan
            ),
            "scheduling": scheduling,
        }

    def schedule_plan(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        mode: str = "iteration",
        max_tasks: int = 3,
        max_estimated_minutes: int = 120,
        enqueue: bool = True,
    ) -> dict[str, Any]:
        normalized_mode = str(
            mode
        ).strip().lower()

        if normalized_mode == "next":
            return self.scheduler.schedule_next(
                plan,
                completed_task_ids=(
                    completed_task_ids
                ),
                failed_task_ids=(
                    failed_task_ids
                ),
                enqueue=enqueue,
            )

        if normalized_mode != "iteration":
            return {
                "success": False,
                "status": "UNSUPPORTED_MODE",
                "mode": normalized_mode,
            }

        return self.scheduler.schedule_iteration(
            plan,
            completed_task_ids=(
                completed_task_ids
            ),
            failed_task_ids=(
                failed_task_ids
            ),
            max_tasks=max(
                1,
                int(max_tasks),
            ),
            max_estimated_minutes=max(
                1,
                int(max_estimated_minutes),
            ),
            enqueue=enqueue,
        )

    def enqueue_plan(
        self,
        plan: ImplementationPlan,
    ) -> dict[str, Any]:
        queue = self.task_queue

        if queue is None:
            return {
                "success": False,
                "status": "QUEUE_UNAVAILABLE",
                "created": 0,
                "duplicates": 0,
            }

        creator = getattr(
            queue,
            "create_unique_task",
            None,
        )

        if not callable(creator):
            return {
                "success": False,
                "status": "QUEUE_INCOMPATIBLE",
                "created": 0,
                "duplicates": 0,
            }

        created = 0
        duplicates = 0
        queue_ids: dict[str, str] = {}

        for task_id in plan.execution_order:
            task = next(
                item
                for item in plan.tasks
                if item.task_id == task_id
            )

            dependencies = [
                queue_ids[dependency]
                for dependency
                in task.dependencies
                if dependency in queue_ids
            ]

            queued_task, was_created = creator(
                title=task.title,
                description=task.description,
                source="software_engineer",
                priority=self._resolve_priority(
                    queue,
                    task.priority,
                ),
                payload={
                    "type": "implementation_task",
                    "objective": plan.objective,
                    "task": task.to_dict(),
                    "roi": task.estimated_roi,
                    "risk": task.estimated_risk,
                },
                tags=[
                    "software-engineer",
                    task.category,
                ],
                dependencies=dependencies,
            )

            queue_ids[
                task.task_id
            ] = str(
                getattr(
                    queued_task,
                    "task_id",
                    task.task_id,
                )
            )

            if was_created:
                created += 1
            else:
                duplicates += 1

        return {
            "success": True,
            "status": "QUEUED",
            "created": created,
            "duplicates": duplicates,
            "task_ids": queue_ids,
        }

    @staticmethod
    def _resolve_priority(
        queue: object,
        priority_name: str,
    ) -> object:
        try:
            module = __import__(
                queue.__class__.__module__,
                fromlist=["TaskPriority"],
            )
            priority_type = getattr(
                module,
                "TaskPriority",
            )
            enum_name = {
                "critical": "CRITICAL",
                "high": "HIGH",
                "normal": "NORMAL",
                "medium": "NORMAL",
                "low": "LOW",
            }.get(
                priority_name.lower(),
                "NORMAL",
            )
            return getattr(
                priority_type,
                enum_name,
            )
        except (
            ImportError,
            AttributeError,
        ):
            return priority_name

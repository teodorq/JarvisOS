from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .implementation_planner import ImplementationPlanner
from .iteration_planner import IterationPlanner
from .models import ImplementationPlan


@dataclass(frozen=True)
class ScheduledTask:
    task_id: str
    title: str
    score: float
    estimated_minutes: int
    category: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "score": self.score,
            "estimated_minutes": self.estimated_minutes,
            "category": self.category,
            "payload": dict(self.payload),
        }


class ImplementationScheduler:

    def __init__(
        self,
        *,
        task_queue: object | None = None,
        implementation_planner: ImplementationPlanner | None = None,
        iteration_planner: IterationPlanner | None = None,
    ) -> None:
        self.task_queue = task_queue
        self.implementation_planner = (
            implementation_planner
            or ImplementationPlanner()
        )
        self.iteration_planner = (
            iteration_planner
            or IterationPlanner(
                implementation_planner=(
                    self.implementation_planner
                )
            )
        )

    def schedule_next(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        enqueue: bool = False,
    ) -> dict[str, Any]:
        selected = self.implementation_planner.select_next(
            plan,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
        )

        if selected is None:
            return {
                "success": False,
                "status": "NO_READY_TASK",
                "scheduled_task": None,
            }

        task = next(
            item
            for item in plan.tasks
            if item.task_id == selected.task_id
        )

        scheduled = ScheduledTask(
            task_id=task.task_id,
            title=task.title,
            score=selected.score,
            estimated_minutes=task.estimated_minutes,
            category=task.category,
            payload=self._build_payload(
                plan=plan,
                task=task,
                score=selected.score,
            ),
        )

        result: dict[str, Any] = {
            "success": True,
            "status": "SCHEDULED",
            "scheduled_task": scheduled.to_dict(),
        }

        if enqueue:
            result["queue"] = self.enqueue_task(
                scheduled
            )

        return result

    def schedule_iteration(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        max_tasks: int = 3,
        max_estimated_minutes: int = 120,
        enqueue: bool = False,
    ) -> dict[str, Any]:
        iteration = self.iteration_planner.build_iteration(
            plan,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
            max_tasks=max_tasks,
            max_estimated_minutes=max_estimated_minutes,
        )

        scheduled_tasks: list[ScheduledTask] = []
        task_map = {
            task.task_id: task
            for task in plan.tasks
        }

        for item in iteration[
            "iteration"
        ][
            "selected_tasks"
        ]:
            task = task_map[item["task_id"]]
            scheduled_tasks.append(
                ScheduledTask(
                    task_id=task.task_id,
                    title=task.title,
                    score=float(item["score"]),
                    estimated_minutes=(
                        task.estimated_minutes
                    ),
                    category=task.category,
                    payload=self._build_payload(
                        plan=plan,
                        task=task,
                        score=float(
                            item["score"]
                        ),
                    ),
                )
            )

        result: dict[str, Any] = {
            "success": bool(
                scheduled_tasks
            ),
            "status": iteration["status"],
            "scheduled_tasks": [
                task.to_dict()
                for task in scheduled_tasks
            ],
            "blocking_report": iteration[
                "blocking_report"
            ],
            "progress": iteration["progress"],
        }

        if enqueue:
            result["queue"] = self.enqueue_tasks(
                scheduled_tasks
            )

        return result

    def enqueue_task(
        self,
        scheduled_task: ScheduledTask,
    ) -> dict[str, Any]:
        return self.enqueue_tasks(
            [scheduled_task]
        )

    def enqueue_tasks(
        self,
        scheduled_tasks: list[ScheduledTask],
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
        task_ids: list[str] = []

        for scheduled in scheduled_tasks:
            queued_task, was_created = creator(
                title=scheduled.title,
                description=(
                    scheduled.payload[
                        "description"
                    ]
                ),
                source="implementation_scheduler",
                priority=self._resolve_priority(
                    queue,
                    scheduled.payload[
                        "priority"
                    ],
                ),
                payload=scheduled.payload,
                tags=[
                    "software-engineer",
                    "scheduled",
                    scheduled.category,
                ],
                dependencies=[],
            )

            queue_task_id = str(
                getattr(
                    queued_task,
                    "task_id",
                    "",
                )
            )

            if queue_task_id:
                task_ids.append(
                    queue_task_id
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
            "task_ids": task_ids,
        }

    @staticmethod
    def _build_payload(
        *,
        plan: ImplementationPlan,
        task,
        score: float,
    ) -> dict[str, Any]:
        return {
            "type": "scheduled_implementation_task",
            "objective": plan.objective,
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "category": task.category,
            "priority": task.priority,
            "estimated_minutes": (
                task.estimated_minutes
            ),
            "estimated_roi": (
                task.estimated_roi
            ),
            "estimated_risk": (
                task.estimated_risk
            ),
            "score": score,
            "dependencies": list(
                task.dependencies
            ),
            "acceptance_criteria": list(
                task.acceptance_criteria
            ),
            "metadata": dict(
                task.metadata
            ),
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

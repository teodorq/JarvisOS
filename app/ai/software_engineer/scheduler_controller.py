from __future__ import annotations

from typing import Any, Iterable

from .implementation_scheduler import (
    ImplementationScheduler,
)
from .models import ImplementationPlan


class SchedulerController:

    COMMAND_PHRASES = (
        "implementation scheduler",
        "schedule implementation",
        "zaplanuj implementację",
        "zaplanuj implementacje",
        "wybierz następne zadanie",
        "wybierz nastepne zadanie",
        "zaplanuj następną iterację",
        "zaplanuj nastepna iteracje",
    )

    def __init__(
        self,
        *,
        task_queue: object | None = None,
    ) -> None:
        self.scheduler = ImplementationScheduler(
            task_queue=task_queue,
        )

    def schedule_next(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        enqueue: bool = True,
    ) -> dict[str, Any]:
        return self.scheduler.schedule_next(
            plan,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
            enqueue=enqueue,
        )

    def schedule_iteration(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
        max_tasks: int = 3,
        max_estimated_minutes: int = 120,
        enqueue: bool = True,
    ) -> dict[str, Any]:
        return self.scheduler.schedule_iteration(
            plan,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
            max_tasks=max_tasks,
            max_estimated_minutes=max_estimated_minutes,
            enqueue=enqueue,
        )

    def handle(
        self,
        command: str,
        *,
        plan: ImplementationPlan | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.can_handle(command):
            return {
                "success": False,
                "status": "UNSUPPORTED_COMMAND",
            }

        if plan is None:
            return {
                "success": False,
                "status": "PLAN_REQUIRED",
            }

        context = dict(context or {})
        mode = str(
            context.get(
                "mode",
                "iteration",
            )
        ).lower()

        completed = context.get(
            "completed_task_ids",
            [],
        )
        failed = context.get(
            "failed_task_ids",
            [],
        )
        enqueue = bool(
            context.get(
                "enqueue",
                True,
            )
        )

        if mode == "next":
            return self.schedule_next(
                plan,
                completed_task_ids=completed,
                failed_task_ids=failed,
                enqueue=enqueue,
            )

        return self.schedule_iteration(
            plan,
            completed_task_ids=completed,
            failed_task_ids=failed,
            max_tasks=max(
                1,
                int(
                    context.get(
                        "max_tasks",
                        3,
                    )
                ),
            ),
            max_estimated_minutes=max(
                1,
                int(
                    context.get(
                        "max_estimated_minutes",
                        120,
                    )
                ),
            ),
            enqueue=enqueue,
        )

    @classmethod
    def can_handle(
        cls,
        command: str,
    ) -> bool:
        normalized = " ".join(
            str(command).lower().split()
        )

        return any(
            phrase in normalized
            for phrase in cls.COMMAND_PHRASES
        )

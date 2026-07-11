from __future__ import annotations

from typing import Any

from app.autodev.autodev_pipeline import AutoDevPipeline
from app.autodev.continuous_improvement_loop import (
    ContinuousImprovementLoop,
)


class ContinuousImprovementCoordinator:

    def __init__(
        self,
        pipeline: AutoDevPipeline,
        improvement_loop: ContinuousImprovementLoop | None = None,
    ) -> None:

        self.pipeline = pipeline

        self.improvement_loop = (
            improvement_loop
            or ContinuousImprovementLoop()
        )

        self.processed_task_ids: set[str] = set()

        self.last_result: dict[str, Any] | None = None

    def process_completed_tasks(
        self,
    ) -> dict[str, Any]:

        completed_tasks = self.pipeline.list_tasks(
            statuses=None,
        )

        new_completed_tasks = []

        for task in completed_tasks:

            status = str(
                task.get(
                    "status",
                    "",
                )
            ).upper()

            task_id = str(
                task.get(
                    "task_id",
                    task.get(
                        "id",
                        "",
                    ),
                )
            ).strip()

            if status != "COMPLETED":
                continue

            if not task_id:
                continue

            if task_id in self.processed_task_ids:
                continue

            self.processed_task_ids.add(
                task_id
            )

            new_completed_tasks.append(
                task
            )

        cycles = []

        for task in new_completed_tasks:

            cycle_result = (
                self.improvement_loop.next_cycle()
            )

            cycles.append(
                {
                    "completed_task": task,
                    "cycle_result": cycle_result,
                }
            )

        result = {
            "success": True,
            "completed_tasks_found": len(
                new_completed_tasks
            ),
            "cycles_started": len(
                cycles
            ),
            "cycles": cycles,
            "processed_task_ids": len(
                self.processed_task_ids
            ),
        }

        self.last_result = dict(
            result
        )

        return result

    def reset(
        self,
    ) -> None:

        self.processed_task_ids.clear()
        self.last_result = None

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "processed_tasks": len(
                self.processed_task_ids
            ),
            "loop": self.improvement_loop.status(),
            "last_result": self.last_result,
        }
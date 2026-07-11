from __future__ import annotations

from typing import Any

from app.autodev.autodev_runtime_scheduler import (
    AutoDevRuntimeScheduler,
)


class AutoDevTaskDispatcher:
    def __init__(
        self,
        scheduler: AutoDevRuntimeScheduler,
    ) -> None:
        self.scheduler = scheduler
        self.last_result: dict[str, Any] | None = None

    def dispatch(
        self,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(task, dict):
            return self._finish(
                {
                    "success": False,
                    "status": "INVALID_TASK",
                }
            )

        goal = str(
            task.get(
                "goal",
                task.get(
                    "description",
                    task.get(
                        "title",
                        "",
                    ),
                ),
            )
        ).strip()

        if not goal:
            return self._finish(
                {
                    "success": False,
                    "status": "EMPTY_GOAL",
                }
            )

        result = self.scheduler.schedule(
            goal,
            metadata={
                "task_id": str(
                    task.get(
                        "task_id",
                        "",
                    )
                ),
                "target": str(
                    task.get(
                        "target",
                        "",
                    )
                ),
                "source": "AutoDevTaskDispatcher",
                **dict(
                    task.get(
                        "metadata"
                    )
                    or {}
                ),
            },
        )

        return self._finish(
            result
        )

    def dispatch_many(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        results = [
            self.dispatch(task)
            for task in tasks
            if isinstance(task, dict)
        ]

        return {
            "success": all(
                item.get("success", False)
                for item in results
            ),
            "status": "DISPATCH_COMPLETED",
            "count": len(results),
            "results": results,
        }

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_result = dict(result)
        return dict(result)

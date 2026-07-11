from __future__ import annotations

from typing import Any

from app.autodev.autodev_cycle_executor import (
    AutoDevCycleExecutor,
)
from app.autodev.autodev_execution_context import (
    AutoDevExecutionContext,
)
from app.autodev.autodev_queue_service import (
    AutoDevQueueService,
)


class AutoDevRuntimeScheduler:
    def __init__(
        self,
        queue_service: AutoDevQueueService,
        cycle_executor: AutoDevCycleExecutor,
    ) -> None:
        self.queue_service = queue_service
        self.cycle_executor = cycle_executor
        self.last_result: dict[str, Any] | None = None

    def schedule(
        self,
        goal: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = AutoDevExecutionContext(
            goal=str(goal).strip(),
            metadata=dict(metadata or {}),
        )

        if not context.goal:
            return {
                "success": False,
                "status": "EMPTY_GOAL",
            }

        item = self.queue_service.enqueue(
            context.to_dict()
        )

        return {
            "success": True,
            "status": "QUEUED",
            "item": item,
            "queue": self.queue_service.status(),
        }

    def run_next(self) -> dict[str, Any]:
        item = self.queue_service.dequeue()

        if item is None:
            result = {
                "success": True,
                "status": "NO_TASKS",
            }
            self.last_result = result
            return result

        context = AutoDevExecutionContext(
            goal=str(item.get("goal", "")),
            source=str(
                item.get(
                    "source",
                    "AutoDevRuntime",
                )
            ),
            dry_run=True,
            approved=False,
            writes_code=False,
            metadata=dict(
                item.get("metadata") or {}
            ),
        )

        result = self.cycle_executor.execute_preview(
            context
        )

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "queue": self.queue_service.status(),
            "executor": self.cycle_executor.status(),
            "last_result": self.last_result,
        }

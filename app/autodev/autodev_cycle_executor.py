from __future__ import annotations

from typing import Any

from app.autodev.autodev_event_bus import AutoDevEventBus
from app.autodev.autodev_execution_context import (
    AutoDevExecutionContext,
)


class AutoDevCycleExecutor:
    def __init__(
        self,
        runtime_service: Any,
        event_bus: AutoDevEventBus | None = None,
    ) -> None:
        self.runtime_service = runtime_service
        self.event_bus = event_bus or AutoDevEventBus()
        self.last_result: dict[str, Any] | None = None

    def execute_preview(
        self,
        context: AutoDevExecutionContext,
    ) -> dict[str, Any]:
        self.event_bus.publish(
            "CYCLE_STARTED",
            context.to_dict(),
        )

        try:
            result = self.runtime_service.run_goal(
                context.goal
            )

            normalized = {
                **dict(result),
                "dry_run": True,
                "approved": False,
                "writes_code": False,
                "context": context.to_dict(),
            }

            self.event_bus.publish(
                "CYCLE_FINISHED",
                normalized,
            )

        except Exception as error:
            normalized = {
                "success": False,
                "status": "FAILED",
                "error": f"{type(error).__name__}: {error}",
                "dry_run": True,
                "approved": False,
                "writes_code": False,
                "context": context.to_dict(),
            }

            self.event_bus.publish(
                "CYCLE_FAILED",
                normalized,
            )

        self.last_result = dict(normalized)
        return normalized

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "events": self.event_bus.status(),
        }

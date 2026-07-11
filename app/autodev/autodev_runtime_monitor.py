from __future__ import annotations

from typing import Any


class AutoDevRuntimeMonitor:
    def __init__(
        self,
        queue_service: Any,
        cycle_executor: Any,
    ) -> None:
        self.queue_service = queue_service
        self.cycle_executor = cycle_executor

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "RUNTIME_MONITOR_READY",
            "queue": self.queue_service.status(),
            "executor": self.cycle_executor.status(),
        }

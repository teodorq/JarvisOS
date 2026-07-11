from __future__ import annotations

from typing import Any

from app.autodev.autodev_runtime_memory import (
    AutoDevRuntimeMemory,
)


class AutoDevMetricsService:
    def __init__(
        self,
        memory: AutoDevRuntimeMemory,
    ) -> None:
        self.memory = memory

    def calculate(self) -> dict[str, Any]:
        total = len(self.memory.records)
        successful = sum(
            1
            for item in self.memory.records
            if item.get("success") is True
        )
        blocked = sum(
            1
            for item in self.memory.records
            if str(item.get("status", "")).upper()
            in {
                "RISK_BLOCKED",
                "EXECUTION_BLOCKED",
                "WAITING_FOR_APPROVAL",
            }
        )

        return {
            "success": True,
            "status": "METRICS_READY",
            "total_cycles": total,
            "successful_cycles": successful,
            "failed_cycles": total - successful,
            "blocked_cycles": blocked,
            "success_rate": (
                round(successful / total, 4)
                if total
                else 0.0
            ),
        }

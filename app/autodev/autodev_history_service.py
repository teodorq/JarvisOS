from __future__ import annotations

from collections import Counter
from typing import Any

from app.autodev.autodev_runtime_memory import (
    AutoDevRuntimeMemory,
)


class AutoDevHistoryService:
    def __init__(
        self,
        memory: AutoDevRuntimeMemory,
    ) -> None:
        self.memory = memory

    def report(self) -> dict[str, Any]:
        by_status: Counter[str] = Counter()

        for item in self.memory.records:
            by_status[
                str(item.get("status", "UNKNOWN"))
            ] += 1

        return {
            "success": True,
            "status": "HISTORY_READY",
            "summary": self.memory.summary(),
            "by_status": dict(by_status),
        }

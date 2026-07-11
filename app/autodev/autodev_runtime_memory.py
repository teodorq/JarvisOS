from __future__ import annotations

from datetime import datetime
from typing import Any


class AutoDevRuntimeMemory:
    def __init__(
        self,
        max_records: int = 200,
    ) -> None:
        self.max_records = max(1, int(max_records))
        self.records: list[dict[str, Any]] = []

    def remember(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = {
            **dict(record),
            "recorded_at": datetime.now().isoformat(),
        }

        self.records.append(normalized)

        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]

        return dict(normalized)

    def last(self) -> dict[str, Any] | None:
        if not self.records:
            return None
        return dict(self.records[-1])

    def summary(self) -> dict[str, Any]:
        successful = sum(
            1
            for item in self.records
            if item.get("success") is True
        )

        return {
            "total": len(self.records),
            "successful": successful,
            "failed": len(self.records) - successful,
            "last": self.last(),
        }

    def clear(self) -> None:
        self.records.clear()

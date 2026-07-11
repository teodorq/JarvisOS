from __future__ import annotations

from datetime import datetime
from typing import Any


class AutoDevLearningMemory:
    def __init__(
        self,
        max_records: int = 500,
    ) -> None:
        self.max_records = max(
            1,
            int(max_records),
        )
        self.records: list[
            dict[str, Any]
        ] = []

    def remember(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = {
            **dict(record),
            "remembered_at": (
                datetime.now().isoformat()
            ),
        }

        self.records.append(
            normalized
        )

        if len(self.records) > self.max_records:
            self.records = self.records[
                -self.max_records:
            ]

        return dict(
            normalized
        )

    def summary(self) -> dict[str, Any]:
        average = 0.0

        if self.records:
            average = sum(
                float(
                    item.get(
                        "quality_score",
                        0.0,
                    )
                    or 0.0
                )
                for item in self.records
            ) / len(self.records)

        return {
            "count": len(self.records),
            "average_quality_score": round(
                average,
                2,
            ),
            "last": (
                dict(self.records[-1])
                if self.records
                else None
            ),
        }

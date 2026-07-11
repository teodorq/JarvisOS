from __future__ import annotations

from collections import Counter
from typing import Any


class AutoDevHistoryAnalyzerV2:
    def analyze(
        self,
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        statuses: Counter[str] = Counter()
        successes = 0

        for record in records:
            if not isinstance(record, dict):
                continue

            status = str(
                record.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper()

            statuses[status] += 1

            if record.get("success") is True:
                successes += 1

        total = sum(statuses.values())

        return {
            "success": True,
            "status": "HISTORY_ANALYZED",
            "total": total,
            "successful": successes,
            "failed": total - successes,
            "success_rate": (
                round(successes / total, 4)
                if total
                else 0.0
            ),
            "by_status": dict(statuses),
        }

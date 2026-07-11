from __future__ import annotations

from collections import Counter
from typing import Any

from app.autodev.improvement_memory import (
    ImprovementMemory,
)


class QualityTrendAnalyzer:
    """
    Analizuje historię wyników AutoDev.

    Moduł nie modyfikuje kodu ani plików projektu.
    """

    SUCCESS_STATUSES = {
        "COMPLETED",
        "DRY_RUN_OK",
        "VALID",
        "CANDIDATE_READY",
        "LOCAL_PROPOSAL_READY",
    }

    FAILURE_STATUSES = {
        "FAILED",
        "PATCH_REJECTED",
        "VALIDATION_FAILED",
        "FAILED_AND_ROLLED_BACK",
        "MODEL_ERROR",
        "MODEL_UNAVAILABLE",
    }

    def __init__(
        self,
        memory: ImprovementMemory,
    ) -> None:
        self.memory = memory
        self.last_result: dict[str, Any] | None = None

    def analyze(
        self,
        *,
        limit: int = 200,
    ) -> dict[str, Any]:

        records = self.memory.list_records(
            limit=limit
        )

        by_status: Counter[str] = Counter()
        success_count = 0
        failure_count = 0
        rollback_count = 0

        for record in records:
            status = str(
                record.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper()

            by_status[status] += 1

            if (
                record.get("success") is True
                or status in self.SUCCESS_STATUSES
            ):
                success_count += 1
            else:
                failure_count += 1

            if "ROLLBACK" in status:
                rollback_count += 1

        total = len(records)

        success_rate = (
            round(success_count / total, 4)
            if total
            else 0.0
        )

        trend = self._trend_label(
            total=total,
            success_rate=success_rate,
            rollback_count=rollback_count,
        )

        result = {
            "success": True,
            "status": "QUALITY_TREND_READY",
            "records_analyzed": total,
            "successful": success_count,
            "failed": failure_count,
            "rollbacks": rollback_count,
            "success_rate": success_rate,
            "trend": trend,
            "by_status": dict(by_status),
            "recommendations": self._recommend(
                total=total,
                success_rate=success_rate,
                rollback_count=rollback_count,
                by_status=dict(by_status),
            ),
        }

        self.last_result = dict(result)
        return result

    def _trend_label(
        self,
        *,
        total: int,
        success_rate: float,
        rollback_count: int,
    ) -> str:

        if total == 0:
            return "NO_DATA"

        if success_rate >= 0.85 and rollback_count == 0:
            return "STRONG"

        if success_rate >= 0.65:
            return "STABLE"

        if success_rate >= 0.4:
            return "MIXED"

        return "WEAK"

    def _recommend(
        self,
        *,
        total: int,
        success_rate: float,
        rollback_count: int,
        by_status: dict[str, int],
    ) -> list[str]:

        recommendations: list[str] = []

        if total == 0:
            recommendations.append(
                "Najpierw wykonaj kilka cykli dry-run."
            )

        if success_rate < 0.65 and total > 0:
            recommendations.append(
                "Utrzymaj ręczną akceptację zmian."
            )

        if rollback_count > 0:
            recommendations.append(
                "Nie wyłączaj automatycznego rollbacku."
            )

        if by_status.get(
            "MODEL_UNAVAILABLE",
            0,
        ) > 0:
            recommendations.append(
                "Skonfiguruj generator LLM przed "
                "złożonymi refaktoryzacjami."
            )

        if not recommendations:
            recommendations.append(
                "System może kontynuować bezpieczny dry-run."
            )

        return recommendations

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "memory": self.memory.summary(),
        }

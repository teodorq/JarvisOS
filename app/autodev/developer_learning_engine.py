from __future__ import annotations

from collections import Counter
from typing import Any

from app.autodev.improvement_memory import (
    ImprovementMemory,
)


class DeveloperLearningEngine:
    """
    Analizuje historię ulepszeń i buduje proste wnioski.

    Nie modyfikuje kodu projektu.
    """

    def __init__(
        self,
        memory: ImprovementMemory,
    ) -> None:

        self.memory = memory
        self.last_result: dict[str, Any] | None = None

    def analyze(
        self,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:

        records = self.memory.list_records(
            limit=limit
        )

        status_counter: Counter[str] = Counter()
        successful = 0
        failed = 0
        lessons: list[str] = []

        for record in records:
            status = str(
                record.get(
                    "status",
                    "UNKNOWN",
                )
            )

            status_counter[
                status
            ] += 1

            if record.get(
                "success"
            ) is True:
                successful += 1
            else:
                failed += 1

            for lesson in record.get(
                "lessons",
                [],
            ):
                text = str(
                    lesson
                ).strip()

                if text:
                    lessons.append(
                        text
                    )

        total = len(
            records
        )

        success_rate = (
            successful / total
            if total > 0
            else 0.0
        )

        result = {
            "success": True,
            "status": "LEARNING_READY",
            "records_analyzed": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "by_status": dict(
                status_counter
            ),
            "recent_lessons": lessons[-20:],
            "recommendations": self._recommend(
                total=total,
                success_rate=success_rate,
                by_status=dict(status_counter),
            ),
        }

        self.last_result = dict(
            result
        )

        return result

    def _recommend(
        self,
        *,
        total: int,
        success_rate: float,
        by_status: dict[str, int],
    ) -> list[str]:

        recommendations: list[str] = []

        if total == 0:
            recommendations.append(
                "Brak danych historycznych. Użyj dry-run."
            )

        if success_rate < 0.5 and total > 0:
            recommendations.append(
                "Zwiększ liczbę walidacji przed wykonaniem."
            )

        if by_status.get(
            "FAILED_AND_ROLLED_BACK",
            0,
        ) > 0:
            recommendations.append(
                "Utrzymaj automatyczny rollback."
            )

        if by_status.get(
            "MODEL_UNAVAILABLE",
            0,
        ) > 0:
            recommendations.append(
                "Skonfiguruj model patch generatora."
            )

        if not recommendations:
            recommendations.append(
                "Kontynuuj w trybie bezpiecznym."
            )

        return recommendations

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "memory": self.memory.summary(),
        }

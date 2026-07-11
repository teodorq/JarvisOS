from __future__ import annotations

from typing import Any


class AutoDevFeedbackEvaluator:
    def evaluate(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        success = bool(
            result.get(
                "success",
                False,
            )
        )

        status = str(
            result.get(
                "status",
                "UNKNOWN",
            )
        ).upper()

        score = 0.0
        lessons: list[str] = []

        if success:
            score += 60.0
            lessons.append(
                "Cykl zakończył się poprawnie."
            )
        else:
            lessons.append(
                "Cykl wymaga poprawy."
            )

        if status in {
            "DRY_RUN_OK",
            "COMPLETED",
            "PREVIEW_ALLOWED",
        }:
            score += 25.0

        if status in {
            "RISK_BLOCKED",
            "EXECUTION_BLOCKED",
        }:
            score += 10.0
            lessons.append(
                "Bramka bezpieczeństwa zadziałała."
            )

        if status in {
            "FAILED",
            "VALIDATION_FAILED",
        }:
            score -= 30.0

        return {
            "success": True,
            "status": "FEEDBACK_READY",
            "cycle_status": status,
            "quality_score": max(
                0.0,
                min(
                    100.0,
                    score,
                ),
            ),
            "lessons": lessons,
        }

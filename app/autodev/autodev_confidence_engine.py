from __future__ import annotations

from typing import Any


class AutoDevConfidenceEngine:
    def calculate(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:

        priority = self._float(
            candidate.get(
                "priority_score",
                0.0,
            )
        )

        value = self._float(
            candidate.get(
                "value_score",
                0.0,
            )
        )

        risk = self._float(
            candidate.get(
                "risk_score",
                0.0,
            )
        )

        score = 50.0
        score += min(priority, 20.0)
        score += min(value, 20.0)
        score -= min(risk, 40.0)

        score = max(
            0.0,
            min(
                100.0,
                round(score, 2),
            ),
        )

        level = (
            "HIGH"
            if score >= 75
            else (
                "MEDIUM"
                if score >= 50
                else "LOW"
            )
        )

        return {
            "success": True,
            "status": "CONFIDENCE_READY",
            "confidence_score": score,
            "confidence_level": level,
        }

    def _float(
        self,
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

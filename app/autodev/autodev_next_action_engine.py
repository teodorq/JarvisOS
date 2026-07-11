from __future__ import annotations

from typing import Any


class AutoDevNextActionEngine:
    def decide(
        self,
        *,
        confidence: dict[str, Any],
        candidate: dict[str, Any],
    ) -> dict[str, Any]:

        confidence_score = float(
            confidence.get(
                "confidence_score",
                0.0,
            )
            or 0.0
        )

        risk_score = float(
            candidate.get(
                "risk_score",
                0.0,
            )
            or 0.0
        )

        if risk_score > 65.0:
            action = "ANALYZE_ONLY"
            status = "RISK_BLOCKED"

        elif confidence_score < 50.0:
            action = "DEFER"
            status = "LOW_CONFIDENCE"

        else:
            action = "SAFE_PREVIEW"
            status = "ACTION_READY"

        return {
            "success": True,
            "status": status,
            "action": action,
            "approved": False,
            "writes_code": False,
        }

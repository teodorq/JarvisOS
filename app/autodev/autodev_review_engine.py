from __future__ import annotations

from typing import Any


class AutoDevReviewEngine:
    """
    Weryfikuje cel przed przekazaniem go do Runtime.
    """

    def __init__(self) -> None:
        self.last_result: dict[str, Any] | None = None

    def review(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any]:

        errors: list[str] = []
        warnings: list[str] = []

        goal_text = str(
            goal.get(
                "goal",
                "",
            )
        ).strip()

        if not goal_text:
            errors.append(
                "Cel jest pusty."
            )

        if len(goal_text) < 5:
            warnings.append(
                "Cel jest bardzo krótki."
            )

        risk_score = self._float(
            goal.get(
                "risk_score",
                0.0,
            )
        )

        if risk_score >= 50:
            warnings.append(
                "Cel ma podwyższone ryzyko."
            )

        result = {
            "success": not errors,
            "status": (
                "REVIEW_PASSED"
                if not errors
                else "REVIEW_FAILED"
            ),
            "goal": dict(goal),
            "errors": errors,
            "warnings": warnings,
            "writes_code": False,
        }

        self.last_result = dict(result)
        return result

    def _float(
        self,
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
        }

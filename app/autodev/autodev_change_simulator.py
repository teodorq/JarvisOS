from __future__ import annotations

from typing import Any


class AutoDevChangeSimulator:
    """
    Symuluje wpływ zmiany bez modyfikowania plików.
    """

    def simulate(
        self,
        *,
        target: str,
        changed_lines: int,
        dependent_modules: int,
        public_api: bool = False,
    ) -> dict[str, Any]:
        changed_lines = max(0, int(changed_lines))
        dependent_modules = max(0, int(dependent_modules))

        risk = 0.0
        reasons: list[str] = []

        risk += min(changed_lines / 10.0, 35.0)
        risk += min(dependent_modules * 5.0, 40.0)

        if public_api:
            risk += 20.0
            reasons.append(
                "Zmiana może wpływać na publiczne API."
            )

        if changed_lines > 300:
            reasons.append(
                "Zmiana obejmuje dużą liczbę linii."
            )

        if dependent_modules > 5:
            reasons.append(
                "Wiele modułów zależy od celu."
            )

        risk = min(round(risk, 2), 100.0)

        level = (
            "CRITICAL"
            if risk >= 75
            else (
                "HIGH"
                if risk >= 50
                else (
                    "MEDIUM"
                    if risk >= 25
                    else "LOW"
                )
            )
        )

        return {
            "success": True,
            "status": "CHANGE_SIMULATED",
            "target": str(target),
            "risk_score": risk,
            "risk_level": level,
            "reasons": reasons,
            "requires_full_tests": (
                level in {"HIGH", "CRITICAL"}
            ),
            "writes_code": False,
        }

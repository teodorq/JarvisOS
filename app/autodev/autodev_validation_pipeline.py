from __future__ import annotations

from typing import Any


class AutoDevValidationPipeline:
    """
    Łączy podstawowe wyniki analizy w jedną decyzję.
    """

    def validate(
        self,
        *,
        project_analysis: dict[str, Any],
        dependency_graph: dict[str, Any],
        simulation: dict[str, Any],
        project_health: dict[str, Any],
    ) -> dict[str, Any]:
        reasons: list[str] = []

        if not project_analysis.get(
            "success",
            False,
        ):
            reasons.append(
                "Analiza projektu zakończyła się błędem."
            )

        if not dependency_graph.get(
            "success",
            False,
        ):
            reasons.append(
                "Graf zależności nie został zbudowany."
            )

        risk_level = str(
            simulation.get(
                "risk_level",
                "UNKNOWN",
            )
        ).upper()

        if risk_level == "CRITICAL":
            reasons.append(
                "Symulacja wykazała krytyczne ryzyko."
            )

        health_level = str(
            project_health.get(
                "health_level",
                "UNKNOWN",
            )
        ).upper()

        if health_level == "CRITICAL":
            reasons.append(
                "Kondycja projektu jest krytyczna."
            )

        valid = not reasons

        return {
            "success": valid,
            "status": (
                "VALIDATION_PASSED"
                if valid
                else "VALIDATION_BLOCKED"
            ),
            "reasons": reasons,
            "requires_approval": True,
            "approved": False,
            "writes_code": False,
        }

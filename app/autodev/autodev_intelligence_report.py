from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AutoDevIntelligenceReport:
    status: str
    selected_task_id: str = ""
    selected_target: str = ""
    decision: str = ""
    risk_level: str = ""
    risk_score: float = 0.0
    recommendations: list[str] = field(default_factory=list)

    @classmethod
    def from_cycle(
        cls,
        cycle: dict[str, Any],
    ) -> "AutoDevIntelligenceReport":

        selected = cycle.get("selected") or {}
        task = selected.get("task") or {}

        return cls(
            status=str(
                cycle.get(
                    "status",
                    "UNKNOWN",
                )
            ),
            selected_task_id=str(
                task.get(
                    "task_id",
                    "",
                )
            ),
            selected_target=str(
                task.get(
                    "target",
                    "",
                )
            ),
            decision=str(
                selected.get(
                    "decision",
                    "",
                )
            ),
            risk_level=str(
                selected.get(
                    "risk_level",
                    selected.get(
                        "predicted_risk_level",
                        "",
                    ),
                )
            ),
            risk_score=float(
                selected.get(
                    "predicted_risk",
                    0.0,
                )
                or 0.0
            ),
            recommendations=list(
                (
                    cycle.get(
                        "base_cycle",
                        {},
                    )
                    or {}
                ).get(
                    "recommendations",
                    [],
                )
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "status": self.status,
            "selected_task_id": self.selected_task_id,
            "selected_target": self.selected_target,
            "decision": self.decision,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "recommendations": list(
                self.recommendations
            ),
        }

    def summary(
        self,
    ) -> str:

        lines = [
            "AUTODEV INTELLIGENCE REPORT",
            f"Status: {self.status}",
            (
                "Task ID: "
                f"{self.selected_task_id or 'brak'}"
            ),
            (
                "Target: "
                f"{self.selected_target or 'brak'}"
            ),
            (
                "Decyzja: "
                f"{self.decision or 'brak'}"
            ),
            (
                "Ryzyko: "
                f"{self.risk_level or 'UNKNOWN'}"
            ),
            f"Risk score: {self.risk_score:.2f}",
        ]

        if self.recommendations:
            lines.append("")
            lines.append("Rekomendacje:")

            for item in self.recommendations:
                lines.append(
                    f"- {item}"
                )

        return "\n".join(
            lines
        )

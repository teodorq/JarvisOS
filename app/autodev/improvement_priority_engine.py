from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.autodev.change_prediction_engine import (
    ChangePredictionEngine,
)


@dataclass(slots=True)
class PrioritizedImprovement:
    task: dict[str, Any]
    priority_score: float
    predicted_risk: float
    value_score: float
    effort_score: float
    final_score: float
    decision: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImprovementPriorityEngine:
    """
    Wybiera najlepsze zadanie do kolejnego cyklu.

    Wyższa wartość i niższe ryzyko zwiększają wynik.
    Moduł nie uruchamia zmian.
    """

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        predictor: ChangePredictionEngine | None = None,
        max_risk_for_execution: float = 65.0,
    ) -> None:

        self.project_root = project_root
        self.max_risk_for_execution = float(
            max_risk_for_execution
        )

        self.predictor = (
            predictor
            or ChangePredictionEngine(
                project_root=project_root
            )
        )

        self.last_result: dict[str, Any] | None = None

    def prioritize(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:

        candidates: list[
            PrioritizedImprovement
        ] = []

        for task in tasks:
            if not isinstance(
                task,
                dict,
            ):
                continue

            target = str(
                task.get(
                    "target",
                    "",
                )
            ).strip()

            if not target:
                continue

            metadata = dict(
                task.get(
                    "metadata"
                )
                or {}
            )

            change_type = str(
                metadata.get(
                    "issue_type",
                    task.get(
                        "issue_type",
                        "MODULE_REFACTOR",
                    ),
                )
            )

            prediction = self.predictor.predict(
                target=target,
                change_type=change_type,
                metadata=metadata,
            )

            if not prediction.success:
                continue

            priority_score = float(
                task.get(
                    "priority_score",
                    0.0,
                )
            )

            value_score = self._value_score(
                task
            )

            effort_score = self._effort_score(
                task
            )

            final_score = round(
                priority_score
                + value_score
                - prediction.risk_score
                - effort_score,
                2,
            )

            decision = (
                "PREVIEW_ONLY"
                if prediction.risk_score
                > self.max_risk_for_execution
                else "READY_FOR_SAFE_GENERATION"
            )

            reasons = [
                f"Priorytet bazowy: {priority_score:.2f}",
                f"Wartość: {value_score:.2f}",
                f"Ryzyko: {prediction.risk_score:.2f}",
                f"Wysiłek: {effort_score:.2f}",
            ]

            candidates.append(
                PrioritizedImprovement(
                    task=dict(task),
                    priority_score=priority_score,
                    predicted_risk=(
                        prediction.risk_score
                    ),
                    value_score=value_score,
                    effort_score=effort_score,
                    final_score=final_score,
                    decision=decision,
                    reasons=reasons,
                )
            )

        candidates.sort(
            key=lambda item: item.final_score,
            reverse=True,
        )

        selected = (
            candidates[0]
            if candidates
            else None
        )

        result = {
            "success": True,
            "status": (
                "IMPROVEMENT_SELECTED"
                if selected is not None
                else "NO_CANDIDATES"
            ),
            "selected": (
                selected.to_dict()
                if selected is not None
                else None
            ),
            "candidates": [
                item.to_dict()
                for item in candidates
            ],
        }

        self.last_result = dict(result)
        return result

    def _value_score(
        self,
        task: dict[str, Any],
    ) -> float:

        severity = str(
            task.get(
                "severity",
                "MEDIUM",
            )
        ).upper()

        values = {
            "CRITICAL": 50.0,
            "HIGH": 35.0,
            "MEDIUM": 20.0,
            "LOW": 10.0,
        }

        return values.get(
            severity,
            15.0,
        )

    def _effort_score(
        self,
        task: dict[str, Any],
    ) -> float:

        metadata = dict(
            task.get(
                "metadata"
            )
            or {}
        )

        try:
            effort = float(
                metadata.get(
                    "estimated_effort",
                    5.0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            effort = 5.0

        return min(
            max(
                effort,
                0.0,
            ),
            30.0,
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": self.project_root,
            "max_risk_for_execution": (
                self.max_risk_for_execution
            ),
            "last_result": self.last_result,
            "predictor": self.predictor.status(),
        }

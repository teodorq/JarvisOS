from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from app.ai.evolution.evolution_learning_memory import (
    EvolutionLearningMemory,
)


@dataclass(slots=True)
class EvolutionTaskScore:
    task_id: str
    title: str
    roi_score: float
    risk_score: float
    success_probability: float
    strategic_priority: float
    learning_bonus: float
    evolution_score: float
    reasons: list[str]
    task: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutonomousEvolutionEngine:
    """Ocena i wybór najlepszego zadania rozwojowego."""

    def __init__(
        self,
        memory: EvolutionLearningMemory | None = None,
        roi_weight: float = 0.35,
        risk_weight: float = 0.25,
        success_weight: float = 0.20,
        strategy_weight: float = 0.15,
        learning_weight: float = 0.05,
    ) -> None:
        self.memory = memory or EvolutionLearningMemory()
        self.roi_weight = float(roi_weight)
        self.risk_weight = float(risk_weight)
        self.success_weight = float(success_weight)
        self.strategy_weight = float(strategy_weight)
        self.learning_weight = float(learning_weight)

    def evaluate_task(
        self,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(task or {})
        metadata = dict(normalized.get("metadata") or {})

        task_id = str(
            normalized.get("task_id")
            or normalized.get("id")
            or normalized.get("title")
            or "unknown"
        )
        title = str(normalized.get("title") or task_id)

        value = self._number(
            normalized.get(
                "value_score",
                metadata.get("value_score", metadata.get("impact", 50.0)),
            ),
            50.0,
        )
        effort = self._number(
            normalized.get(
                "effort_score",
                metadata.get("effort_score", metadata.get("effort", 50.0)),
            ),
            50.0,
        )
        base_priority = self._number(
            normalized.get("priority_score", metadata.get("priority_score", 50.0)),
            50.0,
        )
        explicit_risk = self._number(
            normalized.get(
                "risk_score",
                metadata.get("risk_score", metadata.get("risk", 50.0)),
            ),
            50.0,
        )

        roi_score = self._clamp(
            (value * 0.70)
            + ((100.0 - effort) * 0.30)
        )
        historical = self.memory.statistics_for(task=normalized)
        success_probability = self._clamp(
            historical["success_probability"]
        )
        rollback_rate = self._clamp(
            historical["rollback_rate"]
        )
        risk_score = self._clamp(
            (explicit_risk * 0.70)
            + (rollback_rate * 0.30)
        )
        strategic_priority = self._clamp(base_priority)
        learning_bonus = self._clamp(
            historical["learning_bonus"]
        )

        evolution_score = self._clamp(
            (roi_score * self.roi_weight)
            + ((100.0 - risk_score) * self.risk_weight)
            + (success_probability * self.success_weight)
            + (strategic_priority * self.strategy_weight)
            + (learning_bonus * self.learning_weight)
        )

        reasons = [
            f"ROI={roi_score:.2f}",
            f"ryzyko={risk_score:.2f}",
            f"szansa sukcesu={success_probability:.2f}%",
            f"priorytet strategiczny={strategic_priority:.2f}",
            f"bonus uczenia={learning_bonus:.2f}",
        ]

        return EvolutionTaskScore(
            task_id=task_id,
            title=title,
            roi_score=round(roi_score, 2),
            risk_score=round(risk_score, 2),
            success_probability=round(success_probability, 2),
            strategic_priority=round(strategic_priority, 2),
            learning_bonus=round(learning_bonus, 2),
            evolution_score=round(evolution_score, 2),
            reasons=reasons,
            task=normalized,
        ).to_dict()

    def rank_tasks(
        self,
        tasks: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        scored = [
            self.evaluate_task(task)
            for task in tasks
            if isinstance(task, dict)
        ]
        return sorted(
            scored,
            key=lambda item: (
                item["evolution_score"],
                item["success_probability"],
                -item["risk_score"],
                item["roi_score"],
            ),
            reverse=True,
        )

    def select_best_task(
        self,
        tasks: Iterable[dict[str, Any]],
    ) -> dict[str, Any] | None:
        ranked = self.rank_tasks(tasks)
        return ranked[0] if ranked else None

    def learn_from_result(
        self,
        task: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        return self.memory.remember(task=task, result=result)

    @staticmethod
    def _number(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

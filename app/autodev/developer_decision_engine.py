from __future__ import annotations

from typing import Any

from app.autodev.developer_learning_engine import (
    DeveloperLearningEngine,
)
from app.autodev.developer_strategy_manager import (
    DeveloperStrategyManager,
)


class DeveloperDecisionEngine:
    """
    Łączy strategię i wnioski z pamięci.

    Wynik decyzji określa:
    - czy wykonać tylko analizę,
    - czy przygotować lokalną zmianę,
    - czy użyć modelu,
    - czy wymagać akceptacji.
    """

    def __init__(
        self,
        strategy_manager: DeveloperStrategyManager,
        learning_engine: DeveloperLearningEngine,
    ) -> None:

        self.strategy_manager = strategy_manager
        self.learning_engine = learning_engine
        self.last_result: dict[str, Any] | None = None

    def decide(
        self,
        *,
        issue_type: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        context = dict(
            context or {}
        )

        strategy = self.strategy_manager.select(
            issue_type=issue_type,
            context=context,
        )

        learning = self.learning_engine.analyze(
            limit=100
        )

        confidence = self._confidence(
            strategy=strategy,
            learning=learning,
        )

        action = self._action_for(
            strategy=strategy,
            confidence=confidence,
        )

        result = {
            "success": True,
            "status": "DECISION_READY",
            "issue_type": str(
                issue_type
            ).strip().upper(),
            "action": action,
            "confidence": confidence,
            "requires_approval": bool(
                strategy.get(
                    "requires_approval",
                    True,
                )
            ),
            "safe_execution": bool(
                strategy.get(
                    "safe_execution",
                    True,
                )
            ),
            "auto_rollback": bool(
                strategy.get(
                    "auto_rollback",
                    True,
                )
            ),
            "strategy": strategy,
            "learning": learning,
        }

        self.last_result = dict(
            result
        )

        return result

    def _confidence(
        self,
        *,
        strategy: dict[str, Any],
        learning: dict[str, Any],
    ) -> float:

        base = 0.5

        if strategy.get(
            "name"
        ) == "local_safe_refactor":
            base += 0.25

        success_rate = float(
            learning.get(
                "success_rate",
                0.0,
            )
        )

        if success_rate >= 0.8:
            base += 0.15

        if success_rate < 0.5:
            base -= 0.15

        return max(
            0.0,
            min(
                1.0,
                base,
            ),
        )

    def _action_for(
        self,
        *,
        strategy: dict[str, Any],
        confidence: float,
    ) -> str:

        name = str(
            strategy.get(
                "name",
                "analysis_only",
            )
        )

        if name == "analysis_only":
            return "ANALYZE_ONLY"

        if confidence < 0.4:
            return "ANALYZE_ONLY"

        if strategy.get(
            "requires_llm"
        ):
            return "GENERATE_WITH_LLM"

        return "GENERATE_LOCAL"

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "strategy_manager": (
                self.strategy_manager.status()
            ),
            "learning_engine": (
                self.learning_engine.status()
            ),
        }

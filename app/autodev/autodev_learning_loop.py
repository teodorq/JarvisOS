from __future__ import annotations

from typing import Any

from app.autodev.autodev_feedback_evaluator import (
    AutoDevFeedbackEvaluator,
)
from app.autodev.autodev_learning_memory import (
    AutoDevLearningMemory,
)
from app.autodev.autodev_policy_optimizer import (
    AutoDevPolicyOptimizer,
)


class AutoDevLearningLoop:
    def __init__(
        self,
        evaluator: AutoDevFeedbackEvaluator | None = None,
        memory: AutoDevLearningMemory | None = None,
        optimizer: AutoDevPolicyOptimizer | None = None,
    ) -> None:
        self.evaluator = (
            evaluator
            or AutoDevFeedbackEvaluator()
        )
        self.memory = (
            memory
            or AutoDevLearningMemory()
        )
        self.optimizer = (
            optimizer
            or AutoDevPolicyOptimizer()
        )
        self.last_result: dict[str, Any] | None = None

    def learn(
        self,
        *,
        cycle_result: dict[str, Any],
        current_policy: dict[str, Any],
    ) -> dict[str, Any]:
        feedback = self.evaluator.evaluate(
            cycle_result
        )

        self.memory.remember(
            feedback
        )

        policy_result = self.optimizer.optimize(
            memory_summary=self.memory.summary(),
            current_policy=current_policy,
        )

        result = {
            "success": True,
            "status": "LEARNING_COMPLETED",
            "feedback": feedback,
            "memory": self.memory.summary(),
            "policy": policy_result,
            "writes_code": False,
        }

        self.last_result = dict(
            result
        )

        return result

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "memory": self.memory.summary(),
        }

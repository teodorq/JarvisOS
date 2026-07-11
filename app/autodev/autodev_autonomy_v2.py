from __future__ import annotations

from typing import Any

from app.autodev.autodev_learning_loop import (
    AutoDevLearningLoop,
)


class AutoDevAutonomyV2:
    def __init__(
        self,
        autonomy_coordinator: Any,
        learning_loop: AutoDevLearningLoop | None = None,
    ) -> None:
        self.autonomy_coordinator = (
            autonomy_coordinator
        )
        self.learning_loop = (
            learning_loop
            or AutoDevLearningLoop()
        )
        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cycle = self.autonomy_coordinator.run(
            candidates
        )

        learning = self.learning_loop.learn(
            cycle_result=cycle,
            current_policy={
                "max_risk_score": 65.0,
                "require_approval": True,
                "dry_run": True,
            },
        )

        result = {
            "success": bool(
                cycle.get(
                    "success",
                    False,
                )
            ),
            "status": "AUTONOMY_V2_COMPLETED",
            "cycle": cycle,
            "learning": learning,
            "approved": False,
            "writes_code": False,
        }

        self.last_result = dict(
            result
        )

        return result

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "learning": self.learning_loop.status(),
        }

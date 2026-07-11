from __future__ import annotations

from typing import Any

from app.autodev.autodev_decision_policy import (
    AutoDevDecisionPolicy,
)


class AutoDevAutonomyV7:
    """
    Bezpieczna brama między analizą projektu a wykonaniem zmian.

    Warstwa uruchamia Autonomy V6, wybiera wskazany cel i buduje
    decyzję wymagającą jawnego zatwierdzenia. Nie zapisuje kodu.
    """

    def __init__(
        self,
        autonomy_v6: Any,
        decision_policy: AutoDevDecisionPolicy | None = None,
    ) -> None:
        self.autonomy_v6 = autonomy_v6
        self.decision_policy = (
            decision_policy
            or AutoDevDecisionPolicy()
        )
        self.last_result: dict[str, Any] | None = None

    def run(self) -> dict[str, Any]:
        cycle = self.autonomy_v6.run()

        if not bool(cycle.get("success", False)):
            return self._finish(
                {
                    "success": False,
                    "status": "AUTONOMY_V6_FAILED",
                    "cycle": cycle,
                    "approved": False,
                    "requires_approval": False,
                    "writes_code": False,
                }
            )

        goal = self._selected_goal(cycle)

        if goal is None:
            return self._finish(
                {
                    "success": True,
                    "status": "NO_EXECUTION_CANDIDATE",
                    "cycle": cycle,
                    "approved": False,
                    "requires_approval": False,
                    "writes_code": False,
                }
            )

        decision = self.decision_policy.decide(
            goal
        ).to_dict()

        return self._finish(
            {
                "success": True,
                "status": "AUTONOMY_V7_READY",
                "cycle": cycle,
                "goal": goal,
                "decision": decision,
                "approved": False,
                "requires_approval": bool(
                    decision.get(
                        "requires_approval",
                        True,
                    )
                ),
                "writes_code": False,
            }
        )

    def _selected_goal(
        self,
        cycle: dict[str, Any],
    ) -> dict[str, Any] | None:
        v5_cycle = cycle.get("cycle", {}) or {}
        plan = v5_cycle.get("plan", {}) or {}
        optimized = plan.get("optimized", {}) or {}
        selected = optimized.get("selected")

        if isinstance(selected, dict):
            return dict(selected)

        intelligence = cycle.get(
            "intelligence",
            {},
        ) or {}
        tasks = list(
            intelligence.get(
                "next_tasks",
                [],
            )
        )

        for task in tasks:
            if isinstance(task, dict):
                return dict(task)

        return None

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_result = dict(result)
        return dict(result)

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "decision_policy": (
                self.decision_policy.status()
            ),
        }

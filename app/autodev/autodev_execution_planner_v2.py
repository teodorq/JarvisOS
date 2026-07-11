from __future__ import annotations

from typing import Any


class AutoDevExecutionPlannerV2:
    """
    Tworzy plan wykonania na podstawie celu i decyzji.
    """

    def __init__(self) -> None:
        self.last_result: dict[str, Any] | None = None

    def build(
        self,
        *,
        goal: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:

        if not decision.get(
            "allowed",
            False,
        ):
            result = {
                "success": False,
                "status": "EXECUTION_NOT_ALLOWED",
                "steps": [],
                "writes_code": False,
            }

            self.last_result = dict(result)
            return result

        steps = [
            {
                "step_id": "review",
                "order": 1,
                "action": "REVIEW",
            },
            {
                "step_id": "queue",
                "order": 2,
                "action": "QUEUE",
            },
            {
                "step_id": "preview",
                "order": 3,
                "action": "PREVIEW",
            },
            {
                "step_id": "report",
                "order": 4,
                "action": "REPORT",
            },
        ]

        result = {
            "success": True,
            "status": "EXECUTION_PLAN_READY",
            "goal": dict(goal),
            "decision": dict(decision),
            "steps": steps,
            "approved": False,
            "writes_code": False,
        }

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
        }

from __future__ import annotations

from typing import Any

from app.autodev.autodev_decision_policy import (
    AutoDevDecisionPolicy,
)
from app.autodev.autodev_execution_planner_v2 import (
    AutoDevExecutionPlannerV2,
)
from app.autodev.autodev_goal_planner import (
    AutoDevGoalPlanner,
)
from app.autodev.autodev_review_engine import (
    AutoDevReviewEngine,
)


class AutoDevAutonomyCoordinator:
    """
    Koordynuje wybór celu, decyzję, review i preview.
    """

    def __init__(
        self,
        brain_scheduler: Any,
        goal_planner: AutoDevGoalPlanner | None = None,
        decision_policy: AutoDevDecisionPolicy | None = None,
        review_engine: AutoDevReviewEngine | None = None,
        execution_planner: AutoDevExecutionPlannerV2 | None = None,
    ) -> None:

        self.brain_scheduler = brain_scheduler
        self.goal_planner = (
            goal_planner
            or AutoDevGoalPlanner()
        )
        self.decision_policy = (
            decision_policy
            or AutoDevDecisionPolicy()
        )
        self.review_engine = (
            review_engine
            or AutoDevReviewEngine()
        )
        self.execution_planner = (
            execution_planner
            or AutoDevExecutionPlannerV2()
        )

        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:

        planning = self.goal_planner.plan(
            candidates
        )

        selected = planning.get(
            "selected"
        )

        if not isinstance(selected, dict):
            return self._finish(
                {
                    "success": True,
                    "status": "NO_GOALS",
                    "planning": planning,
                    "writes_code": False,
                    "approved": False,
                }
            )

        review = self.review_engine.review(
            selected
        )

        if not review.get(
            "success",
            False,
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "REVIEW_FAILED",
                    "planning": planning,
                    "review": review,
                    "writes_code": False,
                    "approved": False,
                }
            )

        decision = self.decision_policy.decide(
            selected
        )

        execution_plan = (
            self.execution_planner.build(
                goal=selected,
                decision=decision.to_dict(),
            )
        )

        if not decision.allowed:
            return self._finish(
                {
                    "success": True,
                    "status": decision.status,
                    "planning": planning,
                    "review": review,
                    "decision": decision.to_dict(),
                    "execution_plan": execution_plan,
                    "writes_code": False,
                    "approved": False,
                }
            )

        scheduled = self.brain_scheduler.schedule(
            [
                selected
            ]
        )

        if not scheduled.get(
            "success",
            False,
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "SCHEDULING_FAILED",
                    "planning": planning,
                    "review": review,
                    "decision": decision.to_dict(),
                    "execution_plan": execution_plan,
                    "scheduled": scheduled,
                    "writes_code": False,
                    "approved": False,
                }
            )

        runtime_result = (
            self.brain_scheduler.run_next()
        )

        return self._finish(
            {
                "success": bool(
                    runtime_result.get(
                        "success",
                        False,
                    )
                ),
                "status": str(
                    runtime_result.get(
                        "status",
                        "UNKNOWN",
                    )
                ),
                "planning": planning,
                "review": review,
                "decision": decision.to_dict(),
                "execution_plan": execution_plan,
                "scheduled": scheduled,
                "runtime_result": runtime_result,
                "writes_code": False,
                "approved": False,
            }
        )

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_result = dict(result)
        return dict(result)

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "goal_planner": self.goal_planner.status(),
            "decision_policy": (
                self.decision_policy.status()
            ),
            "review_engine": (
                self.review_engine.status()
            ),
            "execution_planner": (
                self.execution_planner.status()
            ),
            "brain_scheduler": (
                self.brain_scheduler.status()
            ),
        }

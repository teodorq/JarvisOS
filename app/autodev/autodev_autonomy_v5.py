from __future__ import annotations

from typing import Any

from app.autodev.autodev_master_planner_v2 import (
    AutoDevMasterPlannerV2,
)


class AutoDevAutonomyV5:
    def __init__(
        self,
        autonomy_v4: Any,
        master_planner: AutoDevMasterPlannerV2 | None = None,
    ) -> None:
        self.autonomy_v4 = autonomy_v4
        self.master_planner = (
            master_planner
            or AutoDevMasterPlannerV2()
        )
        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        *,
        goals: list[dict[str, Any]],
        history_records: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        plan = self.master_planner.plan(
            goals=goals,
            history_records=list(
                history_records or []
            ),
        )

        selected = (
            plan.get(
                "optimized",
                {},
            )
            or {}
        ).get(
            "selected"
        )

        if not isinstance(selected, dict):
            return self._finish(
                {
                    "success": True,
                    "status": "NO_GOALS",
                    "plan": plan,
                    "writes_code": False,
                    "approved": False,
                }
            )

        goal = str(
            selected.get(
                "goal",
                "",
            )
        ).strip()

        cycle = self.autonomy_v4.run(goal)

        return self._finish(
            {
                "success": bool(
                    cycle.get(
                        "success",
                        False,
                    )
                ),
                "status": "AUTONOMY_V5_COMPLETED",
                "plan": plan,
                "cycle": cycle,
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
            "master_planner": self.master_planner.status(),
        }

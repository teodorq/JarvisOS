from __future__ import annotations

from typing import Any

from app.autodev.autodev_cycle_summary import (
    AutoDevCycleSummary,
)
from app.autodev.autodev_execution_preview import (
    AutoDevExecutionPreview,
)
from app.autodev.autodev_multi_stage_planner import (
    AutoDevMultiStagePlanner,
)


class AutoDevAutonomyV4:
    def __init__(
        self,
        planner: AutoDevMultiStagePlanner | None = None,
        preview_builder: AutoDevExecutionPreview | None = None,
        summary_builder: AutoDevCycleSummary | None = None,
    ) -> None:
        self.planner = (
            planner
            or AutoDevMultiStagePlanner()
        )
        self.preview_builder = (
            preview_builder
            or AutoDevExecutionPreview()
        )
        self.summary_builder = (
            summary_builder
            or AutoDevCycleSummary()
        )
        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        goal: str,
    ) -> dict[str, Any]:
        plan = self.planner.plan(goal)

        if not plan.get("success", False):
            return self._finish(
                {
                    "success": False,
                    "status": "AUTONOMY_V4_BLOCKED",
                    "plan": plan,
                    "approved": False,
                    "writes_code": False,
                }
            )

        preview = self.preview_builder.build(plan)

        summary = self.summary_builder.build(
            plan=plan,
            preview=preview,
        )

        return self._finish(
            {
                "success": bool(
                    summary.get(
                        "success",
                        False,
                    )
                ),
                "status": "AUTONOMY_V4_COMPLETED",
                "plan": plan,
                "preview": preview,
                "summary": summary,
                "approved": False,
                "writes_code": False,
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
            "planner": self.planner.status(),
        }

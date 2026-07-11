from __future__ import annotations

from typing import Any


class AutoDevCycleSummary:
    def build(
        self,
        *,
        plan: dict[str, Any],
        preview: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "success": bool(
                plan.get(
                    "success",
                    False,
                )
                and preview.get(
                    "success",
                    False,
                )
            ),
            "status": "CYCLE_SUMMARY_READY",
            "goal": plan.get(
                "goal",
                "",
            ),
            "plan_status": plan.get(
                "status",
                "UNKNOWN",
            ),
            "preview_status": preview.get(
                "status",
                "UNKNOWN",
            ),
            "steps_count": len(
                preview.get(
                    "steps",
                    [],
                )
                or []
            ),
            "approved": False,
            "writes_code": False,
        }

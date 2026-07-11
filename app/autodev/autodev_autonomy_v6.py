from __future__ import annotations

from typing import Any

from app.autodev.project_intelligence_inspector import (
    ProjectIntelligenceInspector,
)


class AutoDevAutonomyV6:
    def __init__(
        self,
        autonomy_v5: Any,
        inspector: ProjectIntelligenceInspector | None = None,
    ) -> None:
        self.autonomy_v5 = autonomy_v5
        self.inspector = (
            inspector
            or ProjectIntelligenceInspector()
        )
        self.last_result: dict[str, Any] | None = None

    def run(self) -> dict[str, Any]:
        intelligence = self.inspector.inspect()
        goals = list(
            intelligence.get(
                "next_tasks",
                [],
            )
        )

        if not goals:
            return self._finish(
                {
                    "success": True,
                    "status": "NO_PROJECT_TASKS",
                    "intelligence": intelligence,
                    "approved": False,
                    "writes_code": False,
                }
            )

        cycle = self.autonomy_v5.run(
            goals=goals,
            history_records=[],
        )

        return self._finish(
            {
                "success": bool(
                    cycle.get(
                        "success",
                        False,
                    )
                ),
                "status": "AUTONOMY_V6_COMPLETED",
                "intelligence": intelligence,
                "cycle": cycle,
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
            "inspector": self.inspector.status(),
        }

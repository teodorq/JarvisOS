from __future__ import annotations

from typing import Any

from app.autodev.autodev_intelligence_report import (
    AutoDevIntelligenceReport,
)
from app.autodev.autodev_intelligence_v2 import (
    AutoDevIntelligenceV2,
)
from app.autodev.autonomous_improvement_pipeline import (
    AutonomousImprovementPipeline,
)


class AutoDevIntelligenceOrchestrator:
    """
    Łączy Intelligence V2 z Autonomous Improvement Pipeline.

    Zasady bezpieczeństwa:
    - domyślnie wykonuje tylko analizę,
    - nie zatwierdza zmian automatycznie,
    - pipeline uruchamia wyłącznie w trybie preview,
    - decyzja PREVIEW_ONLY nigdy nie przechodzi do wykonania.
    """

    def __init__(
        self,
        intelligence: AutoDevIntelligenceV2,
        improvement_pipeline: AutonomousImprovementPipeline,
    ) -> None:

        self.intelligence = intelligence
        self.improvement_pipeline = improvement_pipeline
        self.last_result: dict[str, Any] | None = None

    def analyze(
        self,
    ) -> dict[str, Any]:

        cycle = self.intelligence.run_cycle()
        report = AutoDevIntelligenceReport.from_cycle(
            cycle
        )

        result = {
            "success": bool(
                cycle.get(
                    "success",
                    False,
                )
            ),
            "status": "ANALYSIS_COMPLETED",
            "cycle": cycle,
            "report": report.to_dict(),
            "summary": report.summary(),
            "writes_code": False,
            "approved": False,
        }

        self.last_result = dict(
            result
        )

        return result

    def preview_selected(
        self,
    ) -> dict[str, Any]:

        analysis = self.analyze()
        cycle = analysis.get(
            "cycle",
            {},
        )

        selected = cycle.get(
            "selected"
        )

        if not isinstance(
            selected,
            dict,
        ):
            return self._finish(
                {
                    "success": True,
                    "status": "NO_SELECTED_TASK",
                    "analysis": analysis,
                    "preview": None,
                    "writes_code": False,
                    "approved": False,
                }
            )

        decision = str(
            selected.get(
                "decision",
                "",
            )
        ).upper()

        task = selected.get(
            "task"
        )

        if not isinstance(
            task,
            dict,
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "INVALID_SELECTED_TASK",
                    "analysis": analysis,
                    "preview": None,
                    "writes_code": False,
                    "approved": False,
                }
            )

        if decision == "PREVIEW_ONLY":
            return self._finish(
                {
                    "success": True,
                    "status": "RISK_BLOCKED",
                    "analysis": analysis,
                    "selected": selected,
                    "preview": None,
                    "writes_code": False,
                    "approved": False,
                }
            )

        preview = self.improvement_pipeline.run(
            [
                dict(task)
            ],
            approved=False,
        )

        return self._finish(
            {
                "success": bool(
                    preview.get(
                        "success",
                        False,
                    )
                ),
                "status": str(
                    preview.get(
                        "status",
                        "PREVIEW_FINISHED",
                    )
                ),
                "analysis": analysis,
                "selected": selected,
                "preview": preview,
                "writes_code": False,
                "approved": False,
            }
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "intelligence": self.intelligence.status(),
            "improvement_pipeline": (
                self.improvement_pipeline.status()
            ),
        }

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        self.last_result = dict(
            result
        )

        return dict(
            result
        )

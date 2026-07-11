from __future__ import annotations

from typing import Any

from app.autodev.autodev_intelligence_service import (
    AutoDevIntelligenceService,
)
from app.autodev.improvement_priority_engine import (
    ImprovementPriorityEngine,
)


class AutoDevIntelligenceV2:
    """
    Rozszerza Intelligence Service o:
    - przewidywanie wpływu,
    - analizę ryzyka zależności,
    - wybór najlepszego zadania.

    Cały cykl działa bez zapisu do kodu.
    """

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        intelligence_service: (
            AutoDevIntelligenceService | None
        ) = None,
        priority_engine: (
            ImprovementPriorityEngine | None
        ) = None,
    ) -> None:

        self.project_root = project_root

        self.intelligence_service = (
            intelligence_service
            or AutoDevIntelligenceService(
                project_root=project_root
            )
        )

        self.priority_engine = (
            priority_engine
            or ImprovementPriorityEngine(
                project_root=project_root
            )
        )

        self.last_result: dict[str, Any] | None = None

    def run_cycle(
        self,
    ) -> dict[str, Any]:

        base_cycle = (
            self.intelligence_service.run_review_cycle()
        )

        tasks = list(
            (
                base_cycle.get(
                    "planning",
                    {},
                )
                or {}
            ).get(
                "tasks",
                [],
            )
        )

        prioritization = self.priority_engine.prioritize(
            tasks
        )

        selected = prioritization.get(
            "selected"
        )

        result = {
            "success": bool(
                base_cycle.get(
                    "success",
                    False,
                )
            ),
            "status": "INTELLIGENCE_V2_COMPLETED",
            "base_cycle": base_cycle,
            "prioritization": prioritization,
            "selected": selected,
            "safe_mode": True,
            "writes_code": False,
            "requires_approval": True,
        }

        self.last_result = dict(result)
        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": self.project_root,
            "last_result": self.last_result,
            "intelligence_service": (
                self.intelligence_service.status()
            ),
            "priority_engine": (
                self.priority_engine.status()
            ),
        }

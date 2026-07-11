from __future__ import annotations

from typing import Any

from app.autodev.autonomous_planner import (
    AutonomousPlanner,
)
from app.autodev.improvement_memory import (
    ImprovementMemory,
)
from app.autodev.quality_trend_analyzer import (
    QualityTrendAnalyzer,
)
from app.autodev.self_review_engine import (
    SelfReviewEngine,
)


class AutoDevIntelligenceService:
    """
    Łączy Self Review, historię jakości i Planner.

    Usługa tylko analizuje oraz przygotowuje rekomendacje.
    Nie zapisuje zmian w kodzie.
    """

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        self_review: SelfReviewEngine | None = None,
        planner: AutonomousPlanner | None = None,
        memory: ImprovementMemory | None = None,
        trend_analyzer: QualityTrendAnalyzer | None = None,
    ) -> None:

        self.project_root = project_root

        self.memory = (
            memory
            or ImprovementMemory(
                storage_path=(
                    f"{project_root}/data/autodev/"
                    "improvement_memory.json"
                )
            )
        )

        self.self_review = (
            self_review
            or SelfReviewEngine(
                project_root=project_root
            )
        )

        self.planner = (
            planner
            or AutonomousPlanner(
                project_root=project_root
            )
        )

        self.trend_analyzer = (
            trend_analyzer
            or QualityTrendAnalyzer(
                memory=self.memory
            )
        )

        self.last_result: dict[str, Any] | None = None

    def run_review_cycle(
        self,
    ) -> dict[str, Any]:

        review = self.self_review.run()
        trend = self.trend_analyzer.analyze()

        planning = self.planner.scan_and_plan(
            context_by_module=self._build_context(
                review=review,
                trend=trend,
            )
        )

        result = {
            "success": bool(
                review.get("success", False)
                and planning.get("success", False)
            ),
            "status": "INTELLIGENCE_CYCLE_COMPLETED",
            "review": review,
            "trend": trend,
            "planning": planning,
            "next_task": planning.get(
                "next_task"
            ),
            "recommendations": self._recommend(
                review=review,
                trend=trend,
                planning=planning,
            ),
            "safe_mode": True,
            "writes_code": False,
        }

        self.last_result = dict(result)
        return result

    def _build_context(
        self,
        *,
        review: dict[str, Any],
        trend: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:

        contexts: dict[str, dict[str, Any]] = {}

        for finding in review.get(
            "findings",
            [],
        ):
            path = str(
                finding.get(
                    "path",
                    "",
                )
            )

            if not path:
                continue

            score = float(
                finding.get(
                    "score",
                    100.0,
                )
            )

            contexts[path] = {
                "estimated_effort": (
                    10.0
                    if score < 60
                    else 5.0
                ),
                "recent_regression": (
                    trend.get("trend")
                    in {
                        "MIXED",
                        "WEAK",
                    }
                ),
                "user_blocking": False,
                "security_related": False,
            }

        return contexts

    def _recommend(
        self,
        *,
        review: dict[str, Any],
        trend: dict[str, Any],
        planning: dict[str, Any],
    ) -> list[str]:

        recommendations: list[str] = []

        if review.get(
            "average_score",
            100.0,
        ) < 75:
            recommendations.append(
                "Skup się na modułach z najniższą oceną."
            )

        recommendations.extend(
            trend.get(
                "recommendations",
                [],
            )
        )

        if planning.get(
            "next_task"
        ) is None:
            recommendations.append(
                "Brak pilnych zadań rozwojowych."
            )

        return list(
            dict.fromkeys(
                str(item)
                for item in recommendations
                if str(item).strip()
            )
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": self.project_root,
            "last_result": self.last_result,
            "self_review": self.self_review.status(),
            "planner": self.planner.status(),
            "trend": self.trend_analyzer.status(),
        }

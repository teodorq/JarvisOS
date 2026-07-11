from __future__ import annotations

from typing import Any

from app.autodev.module_analysis import ModuleAnalysis


class ProjectRefactorSelector:
    def select(
        self,
        analyses: list[ModuleAnalysis],
        *,
        limit: int = 10,
    ) -> dict[str, Any]:
        ordered = sorted(
            analyses,
            key=lambda item: (
                item.score,
                -item.line_count,
                -item.import_count,
            ),
        )

        selected = [
            {
                "path": item.path,
                "category": item.category,
                "score": item.score,
                "quality": item.quality,
                "risk": item.risk,
                "line_count": item.line_count,
                "import_count": item.import_count,
                "findings": list(item.findings),
                "recommendations": list(
                    item.recommendations
                ),
                "priority_score": round(
                    max(0.0, 100.0 - item.score),
                    2,
                ),
            }
            for item in ordered[:max(1, int(limit))]
            if item.score < 90
        ]

        return {
            "success": True,
            "status": (
                "REFACTOR_CANDIDATES_READY"
                if selected
                else "NO_REFACTOR_CANDIDATES"
            ),
            "candidates": selected,
            "count": len(selected),
            "writes_code": False,
        }

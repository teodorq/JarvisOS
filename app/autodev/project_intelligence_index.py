from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from app.autodev.module_analysis import ModuleAnalysis
from app.autodev.project_file import ProjectFile


@dataclass(slots=True)
class ProjectIntelligenceIndex:
    files_count: int
    total_lines: int
    total_classes: int
    total_functions: int
    total_imports: int
    categories: dict[str, int] = field(default_factory=dict)
    lowest_quality_modules: list[dict[str, Any]] = field(
        default_factory=list
    )

    @classmethod
    def build(
        cls,
        project_files: list[ProjectFile],
        analyses: list[ModuleAnalysis],
        *,
        low_quality_limit: int = 10,
    ) -> "ProjectIntelligenceIndex":
        categories = Counter(
            str(item.category)
            for item in project_files
        )

        ordered = sorted(
            analyses,
            key=lambda item: item.score,
        )

        return cls(
            files_count=len(project_files),
            total_lines=sum(
                int(getattr(item, "line_count", 0) or 0)
                for item in project_files
            ),
            total_classes=sum(
                len(item.classes)
                for item in project_files
            ),
            total_functions=sum(
                len(item.functions)
                for item in project_files
            ),
            total_imports=sum(
                len(item.imports)
                for item in project_files
            ),
            categories=dict(categories),
            lowest_quality_modules=[
                {
                    "path": item.path,
                    "category": item.category,
                    "score": item.score,
                    "quality": item.quality,
                    "risk": item.risk,
                    "findings": list(item.findings),
                    "recommendations": list(
                        item.recommendations
                    ),
                }
                for item in ordered[:max(1, low_quality_limit)]
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

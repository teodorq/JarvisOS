from __future__ import annotations

from pathlib import Path

from .dependency_analyzer import DependencyAnalyzer
from .god_object_detector import GodObjectDetector
from .layer_violation_detector import (
    LayerRule,
    LayerViolationDetector,
)
from .source_index import SourceIndex


class ArchitectureSmellAnalyzer:

    def __init__(
        self,
        project_root: str | Path,
        source_root: str = "app",
        layer_rules: tuple[LayerRule, ...] | None = None,
        god_object_detector: GodObjectDetector | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.source_root = source_root

        self.source_index = SourceIndex(
            project_root=self.project_root,
            source_root=source_root,
        )
        self.dependencies = DependencyAnalyzer()
        self.god_objects = (
            god_object_detector
            or GodObjectDetector()
        )
        self.layer_violations = LayerViolationDetector(
            rules=layer_rules,
        )

    def analyze(self) -> dict[str, object]:
        files = self.source_index.build()
        graph = self.dependencies.build_graph(files)

        god_objects = self.god_objects.detect(
            files=files,
            dependency_graph=graph,
        )
        violations = self.layer_violations.detect(graph)

        penalty = (
            len(god_objects) * 12.0
            + len(violations) * 8.0
        )
        score = round(
            max(0.0, 100.0 - penalty),
            2,
        )

        recommendations: list[dict[str, object]] = []

        for finding in god_objects:
            recommendations.append(
                {
                    "type": "split_god_object",
                    "target": (
                        f"{finding.module}."
                        f"{finding.class_name}"
                    ),
                    "priority": "high",
                    "score": finding.score,
                    "reason": (
                        "Klasa skupia zbyt wiele metod, "
                        "atrybutów lub odpowiedzialności."
                    ),
                }
            )

        for violation in violations:
            recommendations.append(
                {
                    "type": "remove_layer_violation",
                    "target": violation.source_module,
                    "priority": "high",
                    "reason": (
                        f"Niedozwolona zależność do "
                        f"{violation.target_module}."
                    ),
                }
            )

        return {
            "god_objects": [
                item.to_dict()
                for item in god_objects
            ],
            "layer_violations": [
                item.to_dict()
                for item in violations
            ],
            "smell_score": score,
            "recommendations": recommendations,
        }

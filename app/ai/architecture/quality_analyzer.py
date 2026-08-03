from __future__ import annotations

from pathlib import Path

from .architecture_recommender import ArchitectureRecommender
from .cohesion_analyzer import CohesionAnalyzer
from .coupling_analyzer import CouplingAnalyzer
from .dependency_analyzer import DependencyAnalyzer
from .source_index import SourceIndex


class ArchitectureQualityAnalyzer:

    def __init__(
        self,
        project_root: str | Path,
        source_root: str = "app",
        high_coupling_threshold: int = 8,
        low_cohesion_threshold: float = 0.35,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.source_root = source_root
        self.high_coupling_threshold = high_coupling_threshold
        self.low_cohesion_threshold = low_cohesion_threshold

        self.source_index = SourceIndex(
            project_root=self.project_root,
            source_root=source_root,
        )
        self.dependencies = DependencyAnalyzer()
        self.coupling = CouplingAnalyzer()
        self.cohesion = CohesionAnalyzer()
        self.recommender = ArchitectureRecommender()

    def analyze(self) -> dict[str, object]:
        files = self.source_index.build()
        graph = self.dependencies.build_graph(files)

        coupling_metrics = self.coupling.analyze(graph)
        cohesion_metrics = self.cohesion.analyze(files)

        recommendations = self.recommender.build(
            coupling_metrics=coupling_metrics,
            cohesion_metrics=cohesion_metrics,
            high_coupling_threshold=self.high_coupling_threshold,
            low_cohesion_threshold=self.low_cohesion_threshold,
        )

        coupling_scores = [
            float(values["score"])
            for values in coupling_metrics.values()
        ]
        cohesion_scores = [
            float(values["score"])
            for values in cohesion_metrics.values()
        ]

        coupling_score = (
            sum(coupling_scores) / len(coupling_scores)
            if coupling_scores
            else 100.0
        )
        cohesion_score = (
            sum(cohesion_scores) / len(cohesion_scores)
            if cohesion_scores
            else 100.0
        )

        overall_score = (
            coupling_score * 0.55
            + cohesion_score * 0.45
        )

        return {
            "coupling": coupling_metrics,
            "cohesion": cohesion_metrics,
            "coupling_score": round(coupling_score, 2),
            "cohesion_score": round(cohesion_score, 2),
            "overall_score": round(overall_score, 2),
            "recommendations": recommendations,
        }

from __future__ import annotations

from pathlib import Path

from .architecture_analyzer import ArchitectureAnalyzer
from .architecture_smell_analyzer import ArchitectureSmellAnalyzer
from .module_split_planner import ModuleSplitPlanner
from .refactor_blueprint import RefactorBlueprintBuilder


class RefactorPlanEngine:

    def __init__(
        self,
        project_root: str | Path,
        source_root: str = "app",
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.source_root = source_root

        self.architecture = ArchitectureAnalyzer(
            project_root=self.project_root,
            source_root=source_root,
        )
        self.smells = ArchitectureSmellAnalyzer(
            project_root=self.project_root,
            source_root=source_root,
        )
        self.split_planner = ModuleSplitPlanner()
        self.blueprints = RefactorBlueprintBuilder()

    def build(self) -> dict[str, object]:
        architecture_report = self.architecture.analyze()
        smell_report = self.smells.analyze()

        split_plans = [
            *self.split_planner.build_from_god_objects(
                smell_report["god_objects"],
            ),
            *self.split_planner.build_from_large_files(
                architecture_report.large_files,
            ),
        ]

        blueprints = self.blueprints.build_batch(
            split_plans,
        )

        return {
            "architecture_score": (
                architecture_report.architecture_score
            ),
            "smell_score": smell_report["smell_score"],
            "split_plans": [
                plan.to_dict()
                for plan in split_plans
            ],
            "blueprints": [
                blueprint.to_dict()
                for blueprint in blueprints
            ],
            "recommended_count": len(blueprints),
        }

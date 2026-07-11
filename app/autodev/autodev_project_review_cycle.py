from __future__ import annotations

from typing import Any

from app.autodev.autodev_change_simulator import (
    AutoDevChangeSimulator,
)
from app.autodev.autodev_dependency_graph_v2 import (
    AutoDevDependencyGraphV2,
)
from app.autodev.autodev_project_analyzer import (
    AutoDevProjectAnalyzer,
)
from app.autodev.autodev_project_health import (
    AutoDevProjectHealth,
)
from app.autodev.autodev_report_generator import (
    AutoDevReportGenerator,
)
from app.autodev.autodev_validation_pipeline import (
    AutoDevValidationPipeline,
)


class AutoDevProjectReviewCycle:
    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
    ) -> None:
        self.analyzer = AutoDevProjectAnalyzer(
            project_root=project_root
        )
        self.dependencies = AutoDevDependencyGraphV2(
            project_root=project_root
        )
        self.simulator = AutoDevChangeSimulator()
        self.health = AutoDevProjectHealth()
        self.validation = AutoDevValidationPipeline()
        self.reporter = AutoDevReportGenerator()
        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        *,
        target: str,
        changed_lines: int,
        dependent_modules: int,
        public_api: bool = False,
    ) -> dict[str, Any]:
        project_analysis = self.analyzer.analyze()
        dependency_graph = self.dependencies.build()

        snapshot = dict(
            project_analysis.get(
                "snapshot",
                {},
            )
        )

        project_health = self.health.evaluate(
            snapshot=snapshot,
            dependency_errors=len(
                dependency_graph.get(
                    "errors",
                    [],
                )
            ),
            failed_tests=0,
        )

        simulation = self.simulator.simulate(
            target=target,
            changed_lines=changed_lines,
            dependent_modules=dependent_modules,
            public_api=public_api,
        )

        validation = self.validation.validate(
            project_analysis=project_analysis,
            dependency_graph=dependency_graph,
            simulation=simulation,
            project_health=project_health,
        )

        report = self.reporter.generate(
            project_analysis=project_analysis,
            project_health=project_health,
            simulation=simulation,
            validation=validation,
        )

        result = {
            "success": bool(
                validation.get(
                    "success",
                    False,
                )
            ),
            "status": (
                "PROJECT_REVIEW_PASSED"
                if validation.get(
                    "success",
                    False,
                )
                else "PROJECT_REVIEW_BLOCKED"
            ),
            "analysis": project_analysis,
            "dependencies": dependency_graph,
            "health": project_health,
            "simulation": simulation,
            "validation": validation,
            "report": report,
            "approved": False,
            "writes_code": False,
        }

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
        }

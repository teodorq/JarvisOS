from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from typing import Any

from app.autodev.code_generation_engine import (
    CodeGenerationEngine,
    CodeGenerationPolicy,
)
from app.autodev.code_improvement_engine import (
    CodeImprovementEngine,
)
from app.autodev.code_improvement_planner import (
    CodeImprovementPlanner,
)
from app.autodev.code_issue_analyzer import (
    CodeIssueAnalyzer,
)
from app.autodev.code_target_selector import (
    CodeTargetSelector,
)
from app.autodev.improvement_selector import (
    ImprovementSelector,
)


class CodeImprovementWorkflow:

    def __init__(
        self,
        project_root: str = default_project_root(),
    ) -> None:

        self.improvement_selector = (
            ImprovementSelector()
        )

        self.engine = CodeImprovementEngine(
            project_root=project_root
        )

        self.target_selector = (
            CodeTargetSelector()
        )

        self.issue_analyzer = (
            CodeIssueAnalyzer()
        )

        self.planner = (
            CodeImprovementPlanner()
        )

        self.generator = CodeGenerationEngine(
            policy=CodeGenerationPolicy(
                project_root=project_root,
                dry_run=True,
            )
        )

        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any]:

        selected_task = (
            self.improvement_selector.select(
                tasks
            )
        )

        if selected_task is None:
            result = {
                "success": True,
                "status": "NO_TASKS",
                "selected_task": None,
            }

            self.last_result = result
            return result

        module_analysis = self.engine.analyze_task(
            selected_task
        )

        if not module_analysis.get(
            "success",
            False,
        ):
            result = {
                "success": False,
                "status": "MODULE_ANALYSIS_FAILED",
                "selected_task": selected_task,
                "module_analysis": module_analysis,
            }

            self.last_result = result
            return result

        target = self.target_selector.select(
            module_analysis
        )

        if target is None:
            result = {
                "success": False,
                "status": "TARGET_SELECTION_FAILED",
                "selected_task": selected_task,
                "module_analysis": module_analysis,
            }

            self.last_result = result
            return result

        issue_analysis = self.issue_analyzer.analyze(
            target
        )

        if not issue_analysis.get(
            "success",
            False,
        ):
            result = {
                "success": False,
                "status": "ISSUE_ANALYSIS_FAILED",
                "selected_task": selected_task,
                "module_analysis": module_analysis,
                "target": target,
                "issue_analysis": issue_analysis,
            }

            self.last_result = result
            return result

        plan = self.planner.build_plan(
            target=target,
            analysis=issue_analysis,
        )

        issue_type = str(
            plan.get(
                "issue_type",
                "",
            )
        ).strip()

        requires_generation = bool(
            plan.get(
                "requires_code_generation",
                False,
            )
        )

        candidate_data = None

        if (
            requires_generation
            and issue_type
        ):
            candidate = self.generator.generate(
                plan
            )

            candidate_data = candidate.to_dict()

            result = {
                "success": candidate.success,
                "status": candidate.status,
                "selected_task": selected_task,
                "module_analysis": module_analysis,
                "target": target,
                "issue_analysis": issue_analysis,
                "plan": plan,
                "candidate": candidate_data,
            }

        else:
            result = {
                "success": bool(
                    plan.get(
                        "success",
                        False,
                    )
                ),
                "status": str(
                    plan.get(
                        "status",
                        "UNKNOWN",
                    )
                ),
                "selected_task": selected_task,
                "module_analysis": module_analysis,
                "target": target,
                "issue_analysis": issue_analysis,
                "plan": plan,
                "candidate": candidate_data,
            }

        self.last_result = dict(
            result
        )

        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "improvement_selector": (
                self.improvement_selector.status()
            ),
            "engine": self.engine.status(),
            "target_selector": (
                self.target_selector.status()
            ),
            "issue_analyzer": (
                self.issue_analyzer.status()
            ),
            "planner": self.planner.status(),
            "generator": self.generator.status(),
        }
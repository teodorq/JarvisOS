from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .cross_module_change_planner import (
    CrossModuleChangePlanner,
)
from .multi_file_refactor_proposal_generator import (
    MultiFileRefactorProposalGenerator,
)
from .multi_file_refactor_workflow import (
    MultiFileRefactorWorkflow,
)


class CrossModuleChangeWorkflow:
    """Plans and executes one atomic change across project subsystems."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        planner: CrossModuleChangePlanner | None = None,
        refactor_workflow: MultiFileRefactorWorkflow | None = None,
        proposal_generator: (
            MultiFileRefactorProposalGenerator | None
        ) = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(
            strict=False
        )
        self.planner = (
            planner
            or CrossModuleChangePlanner(self.project_root)
        )
        self.refactor_workflow = (
            refactor_workflow
            or MultiFileRefactorWorkflow(self.project_root)
        )
        self.proposal_generator = proposal_generator

    def run(
        self,
        objective: str,
        *,
        replacements: dict[str, str] | None = None,
        targets: list[str | Path] | None = None,
        proposal_metadata: dict[str, Any] | None = None,
        auto_execute: bool = True,
        auto_approve: bool = False,
        auto_rollback: bool = True,
        allow_public_symbol_removal: bool = False,
        allow_same_subsystem: bool = False,
        required_subsystems: Iterable[str] = (),
    ) -> dict[str, Any]:
        proposal: dict[str, Any] = {
            "success": True,
            "status": "CROSS_MODULE_PROPOSALS_PROVIDED",
            "replacements": {},
            "proposals": [],
            "errors": [],
        }

        if not isinstance(replacements, dict) or not replacements:
            generator = (
                self.proposal_generator
                or MultiFileRefactorProposalGenerator(
                    self.project_root
                )
            )
            self.proposal_generator = generator
            proposal = generator.generate(
                objective,
                list(targets or []),
                metadata={
                    **dict(proposal_metadata or {}),
                    "operation": "cross_module_change",
                    "cross_module": True,
                },
            )

            if not proposal.get("success", False):
                return {
                    "success": False,
                    "status": "CROSS_MODULE_PROPOSAL_FAILED",
                    "objective": str(objective),
                    "proposal": proposal,
                    "cross_module_plan": {},
                    "feature_blueprint": {},
                    "execution": {},
                    "verification": {},
                    "rollback": {},
                    "errors": list(proposal.get("errors", []) or []),
                }

            replacements = dict(
                proposal.get("replacements", {}) or {}
            )

        try:
            plan = self.planner.plan(
                objective,
                replacements,
                allow_public_symbol_removal=(
                    allow_public_symbol_removal
                ),
                allow_same_subsystem=allow_same_subsystem,
                required_subsystems=required_subsystems,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "CROSS_MODULE_PLANNING_FAILED",
                "objective": str(objective),
                "proposal": proposal,
                "cross_module_plan": {},
                "feature_blueprint": {},
                "execution": {},
                "verification": {},
                "rollback": {},
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
            }

        plan_dict = plan.to_dict()
        blueprint = self._blueprint(plan)

        if plan.blocked:
            return {
                "success": False,
                "status": "CROSS_MODULE_PLAN_BLOCKED",
                "objective": plan.objective,
                "proposal": proposal,
                "cross_module_plan": plan_dict,
                "refactor_plan": (
                    plan.refactor_plan.to_dict()
                ),
                "feature_blueprint": blueprint,
                "impact": self._impact(plan),
                "execution": {},
                "verification": {
                    "success": False,
                    "status": "NOT_EXECUTED",
                    "errors": list(plan.blockers),
                },
                "rollback": {},
                "errors": list(plan.blockers),
            }

        result = self.refactor_workflow.run(
            plan.objective,
            replacements=plan.replacements(),
            proposal_metadata=proposal_metadata,
            auto_execute=auto_execute,
            auto_approve=auto_approve,
            auto_rollback=auto_rollback,
            allow_public_symbol_removal=(
                allow_public_symbol_removal
            ),
        )
        enriched = dict(result)
        enriched["status"] = self._status(
            str(result.get("status", "UNKNOWN"))
        )
        enriched["operation"] = "cross_module_change"
        enriched["proposal"] = proposal
        enriched["cross_module_plan"] = plan_dict
        enriched["refactor_plan"] = (
            plan.refactor_plan.to_dict()
        )
        enriched["feature_blueprint"] = blueprint
        enriched["impact"] = self._impact(plan)
        enriched["module_order"] = list(plan.module_order)
        enriched["validation_batches"] = [
            list(batch)
            for batch in plan.validation_batches
        ]
        enriched["stages"] = [
            {
                "name": "CROSS_MODULE_PLAN",
                "success": True,
                "data": {
                    "subsystems": list(plan.subsystems),
                    "module_order": list(plan.module_order),
                    "risk_level": plan.risk_level,
                },
            },
            *list(result.get("stages", []) or []),
        ]
        return enriched

    def get_run(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:
        return self.refactor_workflow.get_run(run_id)

    def recent_runs(
        self,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.refactor_workflow.recent_runs(
            limit=limit
        )

    @staticmethod
    def _impact(plan) -> dict[str, Any]:
        return {
            "files_count": len(plan.files),
            "subsystem_count": len(plan.subsystems),
            "subsystems": list(plan.subsystems),
            "impacted_files_count": len(
                plan.impacted_files
            ),
            "impacted_files": list(
                plan.impacted_files
            ),
            "dependency_edges": [
                edge.to_dict()
                for edge in plan.dependency_edges
            ],
            "risk_score": plan.estimated_risk,
            "risk_level": plan.risk_level,
            "roi_score": plan.estimated_roi,
            "warnings": list(plan.warnings),
            "blockers": list(plan.blockers),
        }

    @staticmethod
    def _blueprint(plan) -> dict[str, Any]:
        return {
            "feature_name": "CrossModuleChange",
            "package_path": "multiple_subsystems",
            "objective": plan.objective,
            "files": [
                {
                    "relative_path": item.relative_path,
                    "category": "cross_module_refactor",
                    "metadata": {
                        "module_name": item.module_name,
                        "subsystem": (
                            CrossModuleChangePlanner
                            ._subsystem(
                                item.relative_path
                            )
                        ),
                        "changed_symbols": list(
                            item.changed_symbols
                        ),
                    },
                }
                for item in plan.files
            ],
            "metadata": {
                "multi_file": True,
                "cross_module": True,
                "operation": "cross_module_change",
                "subsystems": list(plan.subsystems),
                "module_order": list(plan.module_order),
                "risk_score": plan.estimated_risk,
                "risk_level": plan.risk_level,
            },
        }

    @staticmethod
    def _status(value: str) -> str:
        normalized = str(value).upper()
        mapping = {
            "REFACTOR_PLAN_READY": (
                "CROSS_MODULE_PLAN_READY"
            ),
            "REFACTOR_PREVIEW_READY": (
                "CROSS_MODULE_PREVIEW_READY"
            ),
            "REFACTOR_COMPLETED": (
                "CROSS_MODULE_COMPLETED"
            ),
            "REFACTOR_IMPACT_BLOCKED": (
                "CROSS_MODULE_PLAN_BLOCKED"
            ),
            "REFACTOR_POST_VERIFY_FAILED_AND_ROLLED_BACK": (
                "CROSS_MODULE_POST_VERIFY_FAILED_AND_ROLLED_BACK"
            ),
            "REFACTOR_POST_VERIFY_ROLLBACK_FAILED": (
                "CROSS_MODULE_POST_VERIFY_ROLLBACK_FAILED"
            ),
            "REFACTOR_FAILED_AND_ROLLED_BACK": (
                "CROSS_MODULE_FAILED_AND_ROLLED_BACK"
            ),
        }

        if normalized in mapping:
            return mapping[normalized]

        if normalized.startswith("REFACTOR_"):
            return "CROSS_MODULE_" + normalized.removeprefix(
                "REFACTOR_"
            )

        return normalized

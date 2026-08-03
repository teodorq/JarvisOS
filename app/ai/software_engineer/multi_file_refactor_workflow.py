from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .multi_file_refactor_analyzer import (
    MultiFileRefactorAnalyzer,
)
from .multi_file_refactor_executor import (
    MultiFileRefactorExecutor,
)
from .multi_file_refactor_proposal_generator import (
    MultiFileRefactorProposalGenerator,
)
from .multi_file_refactor_verifier import (
    MultiFileRefactorVerifier,
)
from .multi_file_run_store import (
    MultiFileRunStore,
)
from .refactor_models import (
    MultiFileRefactorPlan,
)


class MultiFileRefactorWorkflow:
    """Analyze, execute, verify, rollback and report a refactor."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        analyzer: MultiFileRefactorAnalyzer | None = None,
        executor: MultiFileRefactorExecutor | None = None,
        proposal_generator: (
            MultiFileRefactorProposalGenerator | None
        ) = None,
        verifier: MultiFileRefactorVerifier | None = None,
        run_store: MultiFileRunStore | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.analyzer = (
            analyzer
            or MultiFileRefactorAnalyzer(
                self.project_root
            )
        )
        self.executor = (
            executor
            or MultiFileRefactorExecutor(
                self.project_root
            )
        )
        self.proposal_generator = (
            proposal_generator
        )
        self.verifier = (
            verifier
            or MultiFileRefactorVerifier(
                self.project_root
            )
        )
        self.run_store = (
            run_store
            or MultiFileRunStore(
                self.project_root,
                filename=(
                    "multi_file_refactor_runs.json"
                ),
            )
        )

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
    ) -> dict[str, Any]:
        run_id = uuid4().hex
        started_at = self._now()
        stages: list[dict[str, Any]] = []
        proposal: dict[str, Any] = {
            "success": True,
            "status": "REFACTOR_PROPOSALS_PROVIDED",
            "proposals": [],
            "errors": [],
        }

        if not isinstance(
            replacements,
            dict,
        ) or not replacements:
            generator = (
                self.proposal_generator
                or MultiFileRefactorProposalGenerator(
                    self.project_root
                )
            )
            self.proposal_generator = generator
            proposal = generator.generate(
                objective,
                list(
                    targets or []
                ),
                metadata=proposal_metadata,
            )
            stages.append(
                self._stage(
                    "PROPOSE",
                    bool(
                        proposal.get(
                            "success",
                            False,
                        )
                    ),
                    {
                        "status": proposal.get(
                            "status",
                            "UNKNOWN",
                        ),
                        "files_count": len(
                            proposal.get(
                                "replacements",
                                {},
                            )
                            or {}
                        ),
                    },
                )
            )

            if not proposal.get(
                "success",
                False,
            ):
                return self._finalize(
                    {
                        "run_id": run_id,
                        "success": False,
                        "status": (
                            "REFACTOR_PROPOSAL_FAILED"
                        ),
                        "objective": str(
                            objective
                        ),
                        "proposal": proposal,
                        "refactor_plan": {},
                        "feature_blueprint": {},
                        "execution": {},
                        "verification": {},
                        "rollback": {},
                        "errors": list(
                            proposal.get(
                                "errors",
                                [],
                            )
                            or []
                        ),
                        "stages": stages,
                        "started_at": started_at,
                    }
                )

            replacements = dict(
                proposal.get(
                    "replacements",
                    {},
                )
                or {}
            )

        try:
            plan = self.analyzer.analyze(
                objective,
                replacements,
                allow_public_symbol_removal=(
                    allow_public_symbol_removal
                ),
            )
            stages.append(
                self._stage(
                    "IMPACT_ANALYSIS",
                    not plan.blocked,
                    {
                        "files_count": len(
                            plan.files
                        ),
                        "impacted_files": len(
                            plan.impacted_files
                        ),
                        "risk_score": (
                            plan.estimated_risk
                        ),
                        "risk_level": (
                            plan.risk_level
                        ),
                    },
                )
            )
        except Exception as error:
            return self._finalize(
                {
                    "run_id": run_id,
                    "success": False,
                    "status": (
                        "REFACTOR_ANALYSIS_FAILED"
                    ),
                    "objective": str(
                        objective
                    ),
                    "refactor_plan": {},
                    "feature_blueprint": {},
                    "execution": {},
                    "verification": {},
                    "rollback": {},
                    "errors": [
                        f"{type(error).__name__}: {error}",
                    ],
                    "stages": stages,
                    "started_at": started_at,
                }
            )

        base = {
            "run_id": run_id,
            "objective": plan.objective,
            "proposal": proposal,
            "refactor_plan": plan.to_dict(),
            "feature_blueprint": (
                self._compatibility_blueprint(
                    plan
                )
            ),
            "impact": {
                "files_count": len(
                    plan.files
                ),
                "impacted_files_count": len(
                    plan.impacted_files
                ),
                "impacted_files": list(
                    plan.impacted_files
                ),
                "risk_score": (
                    plan.estimated_risk
                ),
                "risk_level": (
                    plan.risk_level
                ),
                "warnings": list(
                    plan.warnings
                ),
                "blockers": list(
                    plan.blockers
                ),
            },
            "target_path": "",
            "plan": {
                "tasks": [],
            },
            "queue": {
                "success": True,
                "status": "SKIPPED",
                "created": 0,
                "duplicates": 0,
            },
            "started_at": started_at,
            "stages": stages,
        }

        if plan.blocked:
            return self._finalize(
                {
                    **base,
                    "success": False,
                    "status": (
                        "REFACTOR_IMPACT_BLOCKED"
                    ),
                    "execution": {},
                    "verification": {
                        "success": False,
                        "status": (
                            "NOT_EXECUTED"
                        ),
                        "errors": list(
                            plan.blockers
                        ),
                    },
                    "rollback": {},
                    "errors": list(
                        plan.blockers
                    ),
                }
            )

        if not auto_execute:
            stages.append(
                self._stage(
                    "EXECUTE",
                    True,
                    {
                        "skipped": True,
                    },
                )
            )
            return self._finalize(
                {
                    **base,
                    "success": True,
                    "status": (
                        "REFACTOR_PLAN_READY"
                    ),
                    "execution": {},
                    "verification": {
                        "success": True,
                        "status": (
                            "NOT_EXECUTED"
                        ),
                        "errors": [],
                    },
                    "rollback": {},
                    "errors": [],
                }
            )

        execution = self._execute(
            plan,
            auto_approve=auto_approve,
            auto_rollback=auto_rollback,
        )
        execution_status = str(
            execution.get(
                "status",
                "UNKNOWN",
            )
        ).upper()
        stages.append(
            self._stage(
                "EXECUTE",
                bool(
                    execution.get(
                        "success",
                        False,
                    )
                ),
                {
                    "status": execution_status,
                    "files_count": int(
                        execution.get(
                            "files_count",
                            0,
                        )
                        or 0
                    ),
                },
            )
        )
        verification = self.verifier.verify(
            plan,
            execution,
        )
        stages.append(
            self._stage(
                "VERIFY",
                bool(
                    verification.get(
                        "success",
                        False,
                    )
                ),
                {
                    "status": verification.get(
                        "status",
                        "UNKNOWN",
                    ),
                },
            )
        )
        success = bool(
            execution.get(
                "success",
                False,
            )
        ) and bool(
            verification.get(
                "success",
                False,
            )
        )
        rollback: dict[str, Any] = {}
        final_status = self._final_status(
            execution_status,
            verified=bool(
                verification.get(
                    "success",
                    False,
                )
            ),
        )
        errors = self._unique(
            [
                *list(
                    execution.get(
                        "errors",
                        [],
                    )
                    or []
                ),
                *list(
                    verification.get(
                        "errors",
                        [],
                    )
                    or []
                ),
            ]
        )

        if (
            execution_status == "COMPLETED"
            and not verification.get(
                "success",
                False,
            )
            and auto_rollback
        ):
            rollback = self._rollback_last()
            rollback_success = bool(
                rollback.get(
                    "success",
                    False,
                )
            )
            final_status = (
                "REFACTOR_POST_VERIFY_FAILED_AND_ROLLED_BACK"
                if rollback_success
                else "REFACTOR_POST_VERIFY_ROLLBACK_FAILED"
            )
            success = False
            stages.append(
                self._stage(
                    "ROLLBACK",
                    rollback_success,
                    {
                        "status": rollback.get(
                            "status",
                            "UNKNOWN",
                        ),
                    },
                )
            )

            if rollback_success:
                rollback_verification = (
                    self.verifier.verify(
                        plan,
                        {
                            **execution,
                            "status": (
                                "FAILED_AND_ROLLED_BACK"
                            ),
                        },
                    )
                )
                rollback[
                    "verification"
                ] = rollback_verification

                if not rollback_verification.get(
                    "success",
                    False,
                ):
                    final_status = (
                        "REFACTOR_ROLLBACK_INCOMPLETE"
                    )
                    errors.extend(
                        rollback_verification.get(
                            "errors",
                            [],
                        )
                    )

        return self._finalize(
            {
                **base,
                "success": success,
                "status": final_status,
                "execution": execution,
                "verification": verification,
                "rollback": rollback,
                "errors": self._unique(
                    errors
                ),
            }
        )

    def get_run(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:
        return self.run_store.get(
            run_id
        )

    def recent_runs(
        self,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.run_store.list_recent(
            limit=limit
        )

    def _execute(
        self,
        plan: MultiFileRefactorPlan,
        *,
        auto_approve: bool,
        auto_rollback: bool,
    ) -> dict[str, Any]:
        try:
            return self.executor.execute(
                plan,
                auto_approve=auto_approve,
                auto_rollback=auto_rollback,
            )
        except Exception as error:
            return {
                "success": False,
                "status": (
                    "REFACTOR_EXECUTION_EXCEPTION"
                ),
                "files": [
                    item.relative_path
                    for item in plan.files
                ],
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
            }

    def _rollback_last(
        self,
    ) -> dict[str, Any]:
        controller = getattr(
            self.executor,
            "developer_controller",
            None,
        )
        method = getattr(
            controller,
            "rollback_last",
            None,
        )

        if not callable(
            method
        ):
            return {
                "success": False,
                "status": (
                    "ROLLBACK_UNAVAILABLE"
                ),
                "errors": [
                    "Executor nie udostępnia rollback_last().",
                ],
            }

        try:
            result = method()
        except Exception as error:
            return {
                "success": False,
                "status": (
                    "ROLLBACK_EXCEPTION"
                ),
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
            }

        if hasattr(
            result,
            "as_dict",
        ):
            value = result.as_dict()
            return (
                dict(value)
                if isinstance(
                    value,
                    dict,
                )
                else {}
            )

        if isinstance(
            result,
            dict,
        ):
            return dict(
                result
            )

        return {
            "success": bool(
                getattr(
                    result,
                    "success",
                    False,
                )
            ),
            "status": str(
                getattr(
                    result,
                    "status",
                    "UNKNOWN",
                )
            ),
            "errors": list(
                getattr(
                    result,
                    "errors",
                    [],
                )
                or []
            ),
        }

    def _finalize(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        completed = dict(
            result
        )
        completed["finished_at"] = self._now()
        completed["report_path"] = str(
            self.run_store.path
        )
        completed["stages"] = list(
            completed.get(
                "stages",
                [],
            )
        )
        self.run_store.save(
            completed
        )
        return completed

    @staticmethod
    def _compatibility_blueprint(
        plan: MultiFileRefactorPlan,
    ) -> dict[str, Any]:
        return {
            "feature_name": (
                "MultiFileRefactor"
            ),
            "package_path": (
                "existing_project_files"
            ),
            "objective": plan.objective,
            "files": [
                {
                    "relative_path": (
                        item.relative_path
                    ),
                    "category": "refactor",
                    "metadata": {
                        "changed_symbols": list(
                            item.changed_symbols
                        ),
                    },
                }
                for item in plan.files
            ],
            "metadata": {
                "multi_file": True,
                "operation": "refactor",
                "risk_score": (
                    plan.estimated_risk
                ),
                "risk_level": (
                    plan.risk_level
                ),
            },
        }

    @staticmethod
    def _final_status(
        execution_status: str,
        *,
        verified: bool,
    ) -> str:
        mapping = {
            "PREVIEW_READY": (
                "REFACTOR_PREVIEW_READY"
            ),
            "COMPLETED": (
                "REFACTOR_COMPLETED"
                if verified
                else "REFACTOR_VERIFICATION_FAILED"
            ),
            "FAILED_AND_ROLLED_BACK": (
                "REFACTOR_FAILED_AND_ROLLED_BACK"
            ),
            "APPROVAL_BLOCKED": (
                "REFACTOR_APPROVAL_BLOCKED"
            ),
            "VALIDATION_FAILED": (
                "REFACTOR_VALIDATION_FAILED"
            ),
            "EXECUTION_FAILED": (
                "REFACTOR_EXECUTION_FAILED"
            ),
        }

        return mapping.get(
            execution_status,
            (
                execution_status
                if execution_status.startswith(
                    "REFACTOR_"
                )
                else "REFACTOR_"
                + (
                    execution_status
                    or "UNKNOWN"
                )
            ),
        )

    @staticmethod
    def _stage(
        name: str,
        success: bool,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": str(
                name
            ).upper(),
            "success": bool(
                success
            ),
            "timestamp": (
                MultiFileRefactorWorkflow
                ._now()
            ),
            "data": dict(
                data or {}
            ),
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _unique(
        values: list[Any],
    ) -> list[str]:
        result: list[str] = []

        for value in values:
            text = str(
                value
            ).strip()

            if text and text not in result:
                result.append(
                    text
                )

        return result

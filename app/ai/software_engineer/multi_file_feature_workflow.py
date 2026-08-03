from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import traceback
from typing import Any
from uuid import uuid4

from .feature_planner import FeaturePlanner
from .multi_file_feature_executor import (
    MultiFileFeatureExecutor,
)
from .multi_file_feature_verifier import (
    MultiFileFeatureVerifier,
)
from .multi_file_run_store import MultiFileRunStore


class MultiFileFeatureWorkflow:
    """End-to-end plan, execute, verify, rollback and report workflow."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        feature_planner: FeaturePlanner | None = None,
        feature_executor: MultiFileFeatureExecutor | None = None,
        verifier: MultiFileFeatureVerifier | None = None,
        run_store: MultiFileRunStore | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.feature_planner = (
            feature_planner
            or FeaturePlanner()
        )
        self.feature_executor = (
            feature_executor
            or MultiFileFeatureExecutor(
                self.project_root
            )
        )
        self.verifier = (
            verifier
            or MultiFileFeatureVerifier(
                self.project_root
            )
        )
        self.run_store = (
            run_store
            or MultiFileRunStore(
                self.project_root
            )
        )

    def run(
        self,
        objective: str,
        *,
        feature_name: str | None = None,
        package_path: str | None = None,
        include_controller: bool = True,
        include_repository: bool = False,
        auto_execute: bool = True,
        auto_approve: bool = False,
        auto_rollback: bool = True,
        replacements: dict[str, str] | None = None,
        allow_existing: bool = False,
    ) -> dict[str, Any]:
        run_id = uuid4().hex
        started_at = self._now()
        stages: list[dict[str, Any]] = []

        try:
            blueprint = self.feature_planner.plan(
                objective,
                feature_name=feature_name,
                package_path=package_path,
                include_controller=include_controller,
                include_repository=include_repository,
            )
            stages.append(
                self._stage(
                    "PLAN",
                    True,
                    {
                        "files_count": len(
                            blueprint.files
                        ),
                        "risk": blueprint.estimated_risk,
                    },
                )
            )
        except Exception as error:
            return self._finalize(
                {
                    "run_id": run_id,
                    "success": False,
                    "status": "FEATURE_PLAN_FAILED",
                    "objective": str(objective),
                    "feature_blueprint": {},
                    "execution": {},
                    "verification": {},
                    "rollback": {},
                    "errors": [
                        f"{type(error).__name__}: {error}",
                    ],
                    "traceback": traceback.format_exc(),
                    "stages": stages,
                    "started_at": started_at,
                }
            )

        base = {
            "run_id": run_id,
            "objective": blueprint.objective,
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
            "feature_blueprint": blueprint.to_dict(),
            "started_at": started_at,
            "stages": stages,
        }

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
                    "status": "FEATURE_BLUEPRINT_READY",
                    "execution": {},
                    "verification": {
                        "success": True,
                        "status": "NOT_EXECUTED",
                        "errors": [],
                    },
                    "rollback": {},
                    "errors": [],
                }
            )

        try:
            execution = self.feature_executor.execute(
                blueprint,
                auto_approve=auto_approve,
                auto_rollback=auto_rollback,
                replacements=replacements,
                allow_existing=allow_existing,
            )
        except Exception as error:
            execution = {
                "success": False,
                "status": "FEATURE_EXECUTION_EXCEPTION",
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
                "traceback": traceback.format_exc(),
                "files": [],
            }

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
                    "status": str(
                        execution.get(
                            "status",
                            "UNKNOWN",
                        )
                    ),
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
            blueprint,
            execution,
            allow_existing=allow_existing,
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

        execution_status = str(
            execution.get(
                "status",
                "UNKNOWN",
            )
        ).upper()
        rollback: dict[str, Any] = {}
        final_status = execution_status
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
                "POST_VERIFY_FAILED_AND_ROLLED_BACK"
                if rollback_success
                else "POST_VERIFY_ROLLBACK_FAILED"
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
                        blueprint,
                        {
                            **execution,
                            "status": (
                                "FAILED_AND_ROLLED_BACK"
                            ),
                        },
                        allow_existing=allow_existing,
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
                        "POST_VERIFY_ROLLBACK_INCOMPLETE"
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

    def _rollback_last(
        self,
    ) -> dict[str, Any]:
        controller = getattr(
            self.feature_executor,
            "developer_controller",
            None,
        )
        rollback_method = getattr(
            controller,
            "rollback_last",
            None,
        )

        if not callable(
            rollback_method
        ):
            return {
                "success": False,
                "status": "ROLLBACK_UNAVAILABLE",
                "errors": [
                    "Executor nie udostępnia rollback_last().",
                ],
            }

        try:
            result = rollback_method()
        except Exception as error:
            return {
                "success": False,
                "status": "ROLLBACK_EXCEPTION",
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
                "traceback": traceback.format_exc(),
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

        return (
            dict(result)
            if isinstance(
                result,
                dict,
            )
            else {
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
        )

    def _finalize(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        completed = dict(result)
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
    def _stage(
        name: str,
        success: bool,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": str(name).upper(),
            "success": bool(success),
            "timestamp": MultiFileFeatureWorkflow._now(),
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
            text = str(value).strip()

            if text and text not in result:
                result.append(
                    text
                )

        return result

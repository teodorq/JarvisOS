from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import traceback
from typing import Any
from uuid import uuid4

from app.autodev.developer_validator import (
    DeveloperValidator,
)

from .change_campaign_models import (
    ChangeCampaign,
    ChangeCampaignStage,
    utc_now,
)
from .change_campaign_planner import (
    ChangeCampaignPlanner,
)
from .change_campaign_snapshot import (
    ChangeCampaignSnapshotManager,
)
from .change_campaign_store import (
    ChangeCampaignStore,
)
from .cross_module_change_workflow import (
    CrossModuleChangeWorkflow,
)
from .multi_file_feature_workflow import (
    MultiFileFeatureWorkflow,
)


class ChangeCampaignWorkflow:
    """Checkpointed resumable campaign of cross-module changes."""

    _SUCCESS_STATUSES = {
        "CROSS_MODULE_COMPLETED",
        "COMPLETED",
    }
    _PREVIEW_STATUSES = {
        "CROSS_MODULE_PREVIEW_READY",
        "PREVIEW_READY",
    }
    _TERMINAL_STATUSES = {
        "CAMPAIGN_COMPLETED",
        "CAMPAIGN_ROLLED_BACK",
        "CAMPAIGN_FAILED_AND_ROLLED_BACK",
        "CAMPAIGN_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK",
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        cross_module_workflow: (
            CrossModuleChangeWorkflow | Any | None
        ) = None,
        feature_workflow: (
            MultiFileFeatureWorkflow | Any | None
        ) = None,
        planner: (
            ChangeCampaignPlanner | None
        ) = None,
        store: (
            ChangeCampaignStore | None
        ) = None,
        snapshot_manager: (
            ChangeCampaignSnapshotManager
            | None
        ) = None,
        validator: Any | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.cross_module_workflow = (
            cross_module_workflow
            or CrossModuleChangeWorkflow(
                project_root=self.project_root
            )
        )
        self.feature_workflow = (
            feature_workflow
            or MultiFileFeatureWorkflow(
                project_root=self.project_root
            )
        )
        self.planner = (
            planner
            or ChangeCampaignPlanner(
                self.project_root
            )
        )
        self.store = (
            store
            or ChangeCampaignStore(
                self.project_root
            )
        )
        self.snapshot_manager = (
            snapshot_manager
            or ChangeCampaignSnapshotManager(
                self.project_root
            )
        )
        self.validator = (
            validator
            or DeveloperValidator(
                project_root=self.project_root
            )
        )

    def run(
        self,
        objective: str,
        *,
        stages: list[
            dict[str, Any]
        ],
        campaign_id: str | None = None,
        auto_execute: bool = True,
        auto_approve: bool = False,
        auto_rollback: bool = True,
        final_validation: bool = True,
        max_stages_per_run: int | None = None,
        metadata: dict[
            str,
            Any,
        ] | None = None,
    ) -> dict[str, Any]:
        try:
            campaign = self.planner.plan(
                objective,
                stages,
                campaign_id=campaign_id,
                metadata=metadata,
            )
        except Exception as error:
            return {
                "success": False,
                "status": (
                    "CAMPAIGN_PLANNING_FAILED"
                ),
                "campaign_id": str(
                    campaign_id or ""
                ),
                "campaign": {},
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
                "traceback": traceback.format_exc(),
            }

        existing = self.store.get(
            campaign.campaign_id
        )

        if existing is not None:
            return {
                "success": False,
                "status": (
                    "CAMPAIGN_ALREADY_EXISTS"
                ),
                "campaign_id": (
                    campaign.campaign_id
                ),
                "campaign": existing.to_dict(),
                "errors": [
                    "Kampania o tym identyfikatorze "
                    "już istnieje. Użyj wznowienia."
                ],
            }

        self._checkpoint(
            campaign,
            event="CAMPAIGN_PLANNED",
        )
        self.store.save(campaign)

        if not auto_execute:
            campaign.status = (
                "CAMPAIGN_PLAN_READY"
            )
            self._checkpoint(
                campaign,
                event="PLAN_READY",
            )
            self.store.save(campaign)
            return self._response(
                campaign,
                success=True,
            )

        try:
            self.snapshot_manager.create(
                campaign.campaign_id,
                self._targets(campaign),
            )
        except Exception as error:
            campaign.status = (
                "CAMPAIGN_SNAPSHOT_FAILED"
            )
            campaign.errors.append(
                f"{type(error).__name__}: {error}"
            )
            campaign.metadata["last_traceback"] = traceback.format_exc()
            self._checkpoint(
                campaign,
                event="SNAPSHOT_FAILED",
            )
            self.store.save(campaign)
            return self._response(
                campaign,
                success=False,
            )

        return self._execute(
            campaign,
            auto_approve=auto_approve,
            auto_rollback=auto_rollback,
            final_validation=final_validation,
            max_stages_per_run=(
                max_stages_per_run
            ),
            resumed=False,
        )

    def resume(
        self,
        campaign_id: str,
        *,
        auto_approve: bool = False,
        auto_rollback: bool = True,
        final_validation: bool = True,
        max_stages_per_run: int | None = None,
    ) -> dict[str, Any]:
        campaign = self.store.get(
            campaign_id
        )

        if campaign is None:
            return {
                "success": False,
                "status": (
                    "CAMPAIGN_NOT_FOUND"
                ),
                "campaign_id": str(
                    campaign_id
                ),
                "campaign": {},
                "errors": [
                    "Nie znaleziono kampanii."
                ],
            }

        if campaign.status in {
            "CAMPAIGN_COMPLETED",
            "CAMPAIGN_ROLLED_BACK",
        }:
            return self._response(
                campaign,
                success=True,
            )

        interrupted = [
            stage
            for stage in campaign.stages
            if stage.status == "RUNNING"
        ]

        for stage in interrupted:
            stage.status = "PENDING"
            stage.errors.append(
                "Etap był uruchomiony podczas "
                "przerwania i został zaplanowany "
                "ponownie."
            )

        if interrupted:
            campaign.warnings.append(
                "Odzyskano kampanię po "
                "przerwanym etapie."
            )
            self._checkpoint(
                campaign,
                event="INTERRUPTED_STAGE_RECOVERED",
            )

        if (
            campaign.completed_stage_ids
            and not self.snapshot_manager.exists(
                campaign.campaign_id
            )
        ):
            campaign.status = (
                "CAMPAIGN_SNAPSHOT_MISSING"
            )
            campaign.errors.append(
                "Brak snapshotu potrzebnego do "
                "bezpiecznego wznowienia."
            )
            self.store.save(campaign)
            return self._response(
                campaign,
                success=False,
            )

        if not self.snapshot_manager.exists(
            campaign.campaign_id
        ):
            try:
                self.snapshot_manager.create(
                    campaign.campaign_id,
                    self._targets(campaign),
                )
            except Exception as error:
                campaign.status = (
                    "CAMPAIGN_SNAPSHOT_FAILED"
                )
                campaign.errors.append(
                    f"{type(error).__name__}: {error}"
                )
                campaign.metadata["last_traceback"] = traceback.format_exc()
                self.store.save(campaign)
                return self._response(
                    campaign,
                    success=False,
                )

        self._checkpoint(
            campaign,
            event="CAMPAIGN_RESUMED",
        )
        self.store.save(campaign)

        return self._execute(
            campaign,
            auto_approve=auto_approve,
            auto_rollback=auto_rollback,
            final_validation=final_validation,
            max_stages_per_run=(
                max_stages_per_run
            ),
            resumed=True,
        )

    def rollback(
        self,
        campaign_id: str,
    ) -> dict[str, Any]:
        campaign = self.store.get(
            campaign_id
        )

        if campaign is None:
            return {
                "success": False,
                "status": (
                    "CAMPAIGN_NOT_FOUND"
                ),
                "campaign_id": str(
                    campaign_id
                ),
                "campaign": {},
                "errors": [
                    "Nie znaleziono kampanii."
                ],
            }

        return self._rollback_campaign(
            campaign,
            status_on_success=(
                "CAMPAIGN_ROLLED_BACK"
            ),
        )

    def get_campaign(
        self,
        campaign_id: str,
    ) -> dict[str, Any] | None:
        campaign = self.store.get(
            campaign_id
        )

        return (
            campaign.to_dict()
            if campaign is not None
            else None
        )

    def recent_campaigns(
        self,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.store.list_recent(
            limit=limit
        )

    def _execute(
        self,
        campaign: ChangeCampaign,
        *,
        auto_approve: bool,
        auto_rollback: bool,
        final_validation: bool,
        max_stages_per_run: int | None,
        resumed: bool,
    ) -> dict[str, Any]:
        try:
            safe_limit = self._safe_limit(
                max_stages_per_run
            )
        except Exception as error:
            campaign.status = (
                "CAMPAIGN_POLICY_INVALID"
            )
            campaign.errors.append(
                f"{type(error).__name__}: {error}"
            )
            campaign.metadata["last_traceback"] = traceback.format_exc()
            self._checkpoint(
                campaign,
                event="POLICY_INVALID",
            )
            self.store.save(campaign)
            return self._response(
                campaign,
                success=False,
            )

        executed_now = 0
        campaign.status = (
            "CAMPAIGN_RUNNING"
        )

        for stage_id in campaign.execution_order:
            stage = campaign.stage(
                stage_id
            )

            if stage.status == "COMPLETED":
                continue

            incomplete_dependencies = [
                dependency
                for dependency
                in stage.depends_on
                if campaign.stage(
                    dependency
                ).status != "COMPLETED"
            ]

            if incomplete_dependencies:
                stage.status = "FAILED"
                stage.errors.append(
                    "Niespełnione zależności: "
                    + ", ".join(
                        incomplete_dependencies
                    )
                )
                campaign.status = (
                    "CAMPAIGN_DEPENDENCY_BLOCKED"
                )
                campaign.errors.extend(
                    stage.errors
                )
                self._checkpoint(
                    campaign,
                    event="DEPENDENCY_BLOCKED",
                    stage_id=stage.stage_id,
                )
                self.store.save(campaign)

                if auto_rollback:
                    return self._rollback_campaign(
                        campaign,
                        status_on_success=(
                            "CAMPAIGN_FAILED_AND_ROLLED_BACK"
                        ),
                    )

                return self._response(
                    campaign,
                    success=False,
                )

            stage.status = "RUNNING"
            stage.attempt_count += 1
            stage.started_at = utc_now()
            stage.errors = []
            campaign.current_stage_id = (
                stage.stage_id
            )
            self._checkpoint(
                campaign,
                event="STAGE_STARTED",
                stage_id=stage.stage_id,
            )
            self.store.save(campaign)

            try:
                result = self._run_stage(
                    campaign,
                    stage,
                    auto_approve=auto_approve,
                    resumed=resumed,
                )
            except Exception as error:
                result = {
                    "success": False,
                    "status": (
                        "CAMPAIGN_STAGE_EXCEPTION"
                    ),
                    "errors": [
                        f"{type(error).__name__}: {error}",
                    ],
                    "traceback": traceback.format_exc(),
                }

            stage.result = (
                dict(result)
                if isinstance(
                    result,
                    dict,
                )
                else {
                    "success": False,
                    "status": (
                        "CAMPAIGN_STAGE_INVALID_RESULT"
                    ),
                    "errors": [
                        "Workflow etapu zwrócił "
                        "nieprawidłowy wynik."
                    ],
                }
            )
            result_status = str(
                stage.result.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper()

            if (
                bool(
                    stage.result.get(
                        "success",
                        False,
                    )
                )
                and result_status
                in self._SUCCESS_STATUSES
            ):
                stage.status = "COMPLETED"
                stage.completed_at = utc_now()
                executed_now += 1
                self._checkpoint(
                    campaign,
                    event="STAGE_COMPLETED",
                    stage_id=stage.stage_id,
                )
                self.store.save(campaign)

            elif result_status in self._PREVIEW_STATUSES:
                stage.status = (
                    "PREVIEW_READY"
                )
                campaign.status = (
                    "CAMPAIGN_PREVIEW_READY"
                )
                self._checkpoint(
                    campaign,
                    event="STAGE_PREVIEW_READY",
                    stage_id=stage.stage_id,
                )
                self.store.save(campaign)
                return self._response(
                    campaign,
                    success=True,
                )

            else:
                stage.status = "FAILED"
                stage.completed_at = utc_now()
                stage.errors = [
                    str(item)
                    for item in stage.result.get(
                        "errors",
                        [],
                    )
                ]
                campaign.errors.extend(
                    stage.errors
                )
                campaign.status = (
                    "CAMPAIGN_STAGE_FAILED"
                )
                self._checkpoint(
                    campaign,
                    event="STAGE_FAILED",
                    stage_id=stage.stage_id,
                )
                self.store.save(campaign)

                if auto_rollback:
                    return self._rollback_campaign(
                        campaign,
                        status_on_success=(
                            "CAMPAIGN_FAILED_AND_ROLLED_BACK"
                        ),
                    )

                return self._response(
                    campaign,
                    success=False,
                )

            if (
                safe_limit is not None
                and executed_now
                >= safe_limit
                and campaign.pending_stage_ids
            ):
                campaign.status = (
                    "CAMPAIGN_PAUSED"
                )
                campaign.current_stage_id = ""
                self._checkpoint(
                    campaign,
                    event="CAMPAIGN_PAUSED",
                )
                self.store.save(campaign)
                return self._response(
                    campaign,
                    success=True,
                )

        campaign.current_stage_id = ""
        validation = (
            self._validate_project(
                campaign
            )
            if final_validation
            else {
                "success": True,
                "status": "SKIPPED",
                "errors": [],
            }
        )
        campaign.final_validation = (
            validation
        )

        if not bool(
            validation.get(
                "success",
                False,
            )
        ):
            campaign.status = (
                "CAMPAIGN_FINAL_VALIDATION_FAILED"
            )
            campaign.errors.extend(
                str(item)
                for item in validation.get(
                    "errors",
                    [],
                )
            )
            self._checkpoint(
                campaign,
                event="FINAL_VALIDATION_FAILED",
            )
            self.store.save(campaign)

            if auto_rollback:
                return self._rollback_campaign(
                    campaign,
                    status_on_success=(
                        "CAMPAIGN_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK"
                    ),
                )

            return self._response(
                campaign,
                success=False,
            )

        campaign.status = (
            "CAMPAIGN_COMPLETED"
        )
        campaign.completed_at = (
            utc_now()
        )
        self._checkpoint(
            campaign,
            event="CAMPAIGN_COMPLETED",
        )
        campaign.metadata[
            "snapshot_retained"
        ] = True
        self.store.save(campaign)

        return self._response(
            campaign,
            success=True,
        )

    def _run_stage(
        self,
        campaign: ChangeCampaign,
        stage: ChangeCampaignStage,
        *,
        auto_approve: bool,
        resumed: bool,
    ) -> dict[str, Any]:
        kind = str(
            stage.metadata.get(
                "execution_kind",
                "cross_module_change",
            )
        ).strip().casefold()

        if kind == "validation_only":
            return self._run_validation_stage(
                stage
            )

        if kind == "feature_creation":
            return self.feature_workflow.run(
                stage.objective,
                feature_name=str(
                    stage.metadata.get(
                        "feature_name",
                        "",
                    )
                ).strip() or None,
                package_path=str(
                    stage.metadata.get(
                        "package_path",
                        "",
                    )
                ).strip() or None,
                include_controller=bool(
                    stage.metadata.get(
                        "include_controller",
                        True,
                    )
                ),
                include_repository=bool(
                    stage.metadata.get(
                        "include_repository",
                        False,
                    )
                ),
                auto_execute=True,
                auto_approve=bool(
                    stage.auto_approve
                    or auto_approve
                ),
                auto_rollback=True,
                replacements=(
                    dict(stage.replacements)
                    or None
                ),
                allow_existing=bool(
                    stage.metadata.get(
                        "allow_existing",
                        False,
                    )
                ),
            )

        return self.cross_module_workflow.run(
            stage.objective,
            replacements=(
                dict(stage.replacements)
                or None
            ),
            targets=list(stage.targets),
            proposal_metadata={
                **dict(stage.metadata),
                "campaign_id": campaign.campaign_id,
                "campaign_stage_id": stage.stage_id,
                "campaign_resume": resumed,
            },
            auto_execute=True,
            auto_approve=bool(
                stage.auto_approve
                or auto_approve
            ),
            auto_rollback=True,
            allow_public_symbol_removal=(
                stage.allow_public_symbol_removal
            ),
            allow_same_subsystem=(
                stage.allow_same_subsystem
            ),
            required_subsystems=(
                stage.required_subsystems
            ),
        )

    def _run_validation_stage(
        self,
        stage: ChangeCampaignStage,
    ) -> dict[str, Any]:
        full_suite = bool(
            stage.metadata.get(
                "full_suite",
                False,
            )
        )

        try:
            result = self.validator.run_test_suite(
                changed_files=list(stage.targets),
                full_suite=full_suite,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "VALIDATION_STAGE_EXCEPTION",
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
                "traceback": traceback.format_exc(),
            }

        if hasattr(result, "as_dict"):
            value = result.as_dict()
        elif isinstance(result, dict):
            value = dict(result)
        else:
            value = {
                "success": False,
                "errors": [
                    "Walidator zwrócił nieprawidłowy wynik.",
                ],
            }

        value.setdefault(
            "status",
            (
                "COMPLETED"
                if value.get("success", False)
                else "VALIDATION_STAGE_FAILED"
            ),
        )
        value.setdefault("errors", [])
        value["validation_only"] = True
        value["full_suite"] = full_suite
        return value

    def _validate_project(
        self,
        campaign: ChangeCampaign,
    ) -> dict[str, Any]:
        try:
            result = self.validator.run_test_suite(
                changed_files=(
                    self._targets(
                        campaign
                    )
                ),
                full_suite=True,
            )
        except Exception as error:
            return {
                "success": False,
                "status": (
                    "FINAL_VALIDATION_EXCEPTION"
                ),
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
        elif isinstance(
            result,
            dict,
        ):
            value = dict(result)
        else:
            value = {
                "success": False,
                "status": (
                    "FINAL_VALIDATION_INVALID_RESULT"
                ),
                "errors": [
                    "Walidator zwrócił "
                    "nieprawidłowy wynik."
                ],
            }

        value.setdefault(
            "status",
            (
                "FINAL_VALIDATION_PASSED"
                if value.get(
                    "success",
                    False,
                )
                else "FINAL_VALIDATION_FAILED"
            ),
        )
        value.setdefault(
            "errors",
            [],
        )

        return value

    def _rollback_campaign(
        self,
        campaign: ChangeCampaign,
        *,
        status_on_success: str,
    ) -> dict[str, Any]:
        rollback = (
            self.snapshot_manager.restore(
                campaign.campaign_id
            )
        )
        campaign.rollback = dict(
            rollback
        )

        if rollback.get(
            "success",
            False,
        ):
            for stage in campaign.stages:
                if stage.status in {
                    "COMPLETED",
                    "FAILED",
                    "RUNNING",
                }:
                    stage.status = (
                        "ROLLED_BACK"
                    )

            campaign.status = (
                status_on_success
            )
            campaign.completed_at = (
                utc_now()
            )
            self._checkpoint(
                campaign,
                event="CAMPAIGN_ROLLED_BACK",
            )
            self.store.save(campaign)
            self.snapshot_manager.cleanup(
                campaign.campaign_id
            )
            return self._response(
                campaign,
                success=(
                    status_on_success
                    == "CAMPAIGN_ROLLED_BACK"
                ),
            )

        campaign.status = (
            "CAMPAIGN_ROLLBACK_FAILED"
        )
        campaign.errors.extend(
            str(item)
            for item in rollback.get(
                "errors",
                [],
            )
        )
        self._checkpoint(
            campaign,
            event="CAMPAIGN_ROLLBACK_FAILED",
        )
        self.store.save(campaign)

        return self._response(
            campaign,
            success=False,
        )

    def _checkpoint(
        self,
        campaign: ChangeCampaign,
        *,
        event: str,
        stage_id: str = "",
    ) -> None:
        checkpoint = {
            "checkpoint_id": (
                f"checkpoint-{uuid4().hex}"
            ),
            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "event": str(event),
            "stage_id": str(stage_id),
            "campaign_status": (
                campaign.status
            ),
            "completed_stage_ids": list(
                campaign.completed_stage_ids
            ),
            "pending_stage_ids": list(
                campaign.pending_stage_ids
            ),
        }
        campaign.checkpoints.append(
            checkpoint
        )

        if len(
            campaign.checkpoints
        ) > 200:
            campaign.checkpoints = (
                campaign.checkpoints[-200:]
            )

    def _response(
        self,
        campaign: ChangeCampaign,
        *,
        success: bool,
    ) -> dict[str, Any]:
        last_checkpoint = (
            dict(
                campaign.checkpoints[-1]
            )
            if campaign.checkpoints
            else {}
        )

        return {
            "success": bool(success),
            "status": campaign.status,
            "operation": "change_campaign",
            "campaign_id": (
                campaign.campaign_id
            ),
            "campaign": campaign.to_dict(),
            "checkpoint": last_checkpoint,
            "completed_stages": len(
                campaign.completed_stage_ids
            ),
            "stages_count": len(
                campaign.stages
            ),
            "final_validation": dict(
                campaign.final_validation
            ),
            "rollback": dict(
                campaign.rollback
            ),
            "report_path": str(
                self.store.path
            ),
            "snapshot_path": (
                self.snapshot_manager
                .snapshot_path(
                    campaign.campaign_id
                )
            ),
            "errors": list(
                campaign.errors
            ),
        }

    @staticmethod
    def _targets(
        campaign: ChangeCampaign,
    ) -> list[str]:
        return list(
            dict.fromkeys(
                path
                for stage in campaign.stages
                for path in stage.targets
            )
        )

    @staticmethod
    def _safe_limit(
        value: int | None,
    ) -> int | None:
        if value is None:
            return None

        limit = int(value)

        if limit <= 0:
            raise ValueError(
                "max_stages_per_run musi "
                "być większe od zera."
            )

        return min(
            20,
            limit,
        )

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import traceback
from typing import Any
from uuid import uuid4

from app.autodev.developer_validator import DeveloperValidator

from .change_campaign_workflow import ChangeCampaignWorkflow
from .multi_campaign_models import ManagedCampaign, MultiCampaignPortfolio
from .multi_campaign_planner import MultiCampaignPlanner
from .multi_campaign_scheduler import MultiCampaignScheduler
from .multi_campaign_store import MultiCampaignStore


class MultiCampaignWorkflow:
    """Priority-aware, resumable orchestration of many change campaigns."""

    COMPLETED_STATUSES = {"CAMPAIGN_COMPLETED"}
    PAUSED_STATUSES = {
        "CAMPAIGN_PAUSED",
        "CAMPAIGN_PREVIEW_READY",
        "CAMPAIGN_PLAN_READY",
    }
    TERMINAL_STATUSES = {
        "MULTI_CAMPAIGN_COMPLETED",
        "MULTI_CAMPAIGN_ROLLED_BACK",
        "MULTI_CAMPAIGN_FAILED_AND_ROLLED_BACK",
        "MULTI_CAMPAIGN_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK",
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        campaign_workflow: ChangeCampaignWorkflow | Any | None = None,
        planner: MultiCampaignPlanner | None = None,
        scheduler: MultiCampaignScheduler | None = None,
        store: MultiCampaignStore | None = None,
        validator: Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.campaign_workflow = campaign_workflow or ChangeCampaignWorkflow(
            project_root=self.project_root
        )
        self.planner = planner or MultiCampaignPlanner(self.project_root)
        self.scheduler = scheduler or MultiCampaignScheduler()
        self.store = store or MultiCampaignStore(self.project_root)
        self.validator = validator or DeveloperValidator(project_root=self.project_root)

    def run(
        self,
        objective: str,
        *,
        campaigns: list[dict[str, Any]],
        portfolio_id: str | None = None,
        auto_execute: bool = True,
        auto_approve: bool = False,
        auto_rollback: bool = True,
        final_validation: bool = True,
        continue_on_failure: bool = False,
        rollback_completed_on_failure: bool = True,
        max_campaigns_per_run: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            portfolio = self.planner.plan(
                objective,
                campaigns,
                portfolio_id=portfolio_id,
                metadata=metadata,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "MULTI_CAMPAIGN_PLANNING_FAILED",
                "portfolio_id": str(portfolio_id or ""),
                "portfolio": {},
                "errors": [f"{type(error).__name__}: {error}"],
                "traceback": traceback.format_exc(),
            }

        existing = self.store.get(portfolio.portfolio_id)
        if existing is not None:
            return {
                "success": False,
                "status": "MULTI_CAMPAIGN_ALREADY_EXISTS",
                "portfolio_id": portfolio.portfolio_id,
                "portfolio": existing.to_dict(),
                "errors": ["Portfolio o tym identyfikatorze już istnieje."],
            }

        for item in portfolio.campaigns:
            item.metadata["portfolio_id"] = portfolio.portfolio_id

        portfolio.metadata["policy"] = {
            "auto_approve": bool(auto_approve),
            "auto_rollback": bool(auto_rollback),
            "final_validation": bool(final_validation),
            "continue_on_failure": bool(continue_on_failure),
            "rollback_completed_on_failure": bool(rollback_completed_on_failure),
        }
        self._checkpoint(portfolio, event="PORTFOLIO_PLANNED")
        self.store.save(portfolio)

        if not auto_execute:
            portfolio.status = "MULTI_CAMPAIGN_PLAN_READY"
            self._checkpoint(portfolio, event="PORTFOLIO_PLAN_READY")
            self.store.save(portfolio)
            return self._response(portfolio, success=True)

        return self._execute(
            portfolio,
            auto_approve=auto_approve,
            auto_rollback=auto_rollback,
            final_validation=final_validation,
            continue_on_failure=continue_on_failure,
            rollback_completed_on_failure=rollback_completed_on_failure,
            max_campaigns_per_run=max_campaigns_per_run,
        )

    def resume(
        self,
        portfolio_id: str,
        *,
        auto_approve: bool | None = None,
        auto_rollback: bool | None = None,
        final_validation: bool | None = None,
        continue_on_failure: bool | None = None,
        rollback_completed_on_failure: bool | None = None,
        max_campaigns_per_run: int | None = None,
    ) -> dict[str, Any]:
        portfolio = self.store.get(portfolio_id)
        if portfolio is None:
            return self._not_found(portfolio_id)
        if portfolio.status in self.TERMINAL_STATUSES:
            return self._response(portfolio, success=True)

        interrupted = [item for item in portfolio.campaigns if item.status == "RUNNING"]
        for item in interrupted:
            item.status = "PENDING"
            item.warnings.append(
                "Kampania była uruchomiona podczas przerwania i została wznowiona."
            )
        if interrupted:
            portfolio.warnings.append("Odzyskano portfolio po przerwanym wykonaniu.")
            self._checkpoint(portfolio, event="INTERRUPTED_CAMPAIGN_RECOVERED")

        policy = dict(portfolio.metadata.get("policy", {}) or {})
        values = {
            "auto_approve": self._override(auto_approve, policy.get("auto_approve", False)),
            "auto_rollback": self._override(auto_rollback, policy.get("auto_rollback", True)),
            "final_validation": self._override(final_validation, policy.get("final_validation", True)),
            "continue_on_failure": self._override(
                continue_on_failure,
                policy.get("continue_on_failure", False),
            ),
            "rollback_completed_on_failure": self._override(
                rollback_completed_on_failure,
                policy.get("rollback_completed_on_failure", True),
            ),
        }
        portfolio.status = "MULTI_CAMPAIGN_RESUMED"
        self._checkpoint(portfolio, event="PORTFOLIO_RESUMED")
        self.store.save(portfolio)
        return self._execute(
            portfolio,
            max_campaigns_per_run=max_campaigns_per_run,
            **values,
        )

    def rollback(self, portfolio_id: str) -> dict[str, Any]:
        portfolio = self.store.get(portfolio_id)
        if portfolio is None:
            return self._not_found(portfolio_id)
        return self._rollback_portfolio(
            portfolio,
            status_on_success="MULTI_CAMPAIGN_ROLLED_BACK",
        )

    def reprioritize(
        self,
        portfolio_id: str,
        priorities: dict[str, Any],
    ) -> dict[str, Any]:
        portfolio = self.store.get(portfolio_id)
        if portfolio is None:
            return self._not_found(portfolio_id)
        if not isinstance(priorities, dict) or not priorities:
            return {
                **self._response(portfolio, success=False),
                "status": "MULTI_CAMPAIGN_PRIORITIES_REQUIRED",
                "errors": ["Podaj mapę campaign_id -> priority."],
            }

        changed: list[str] = []
        for campaign_id, value in priorities.items():
            try:
                item = portfolio.campaign(str(campaign_id))
            except KeyError:
                portfolio.warnings.append(f"Pominięto nieznaną kampanię: {campaign_id}")
                continue
            if item.status not in {"PENDING", "PAUSED", "BLOCKED"}:
                continue
            priority, score = self.planner.normalize_priority(value)
            item.priority = priority
            item.priority_score = score
            changed.append(item.campaign_id)

        self.scheduler.recalculate_order(portfolio)
        self._checkpoint(
            portfolio,
            event="PORTFOLIO_REPRIORITIZED",
            metadata={"changed_campaign_ids": changed},
        )
        self.store.save(portfolio)
        return self._response(portfolio, success=True)

    def pause(self, portfolio_id: str) -> dict[str, Any]:
        portfolio = self.store.get(portfolio_id)
        if portfolio is None:
            return self._not_found(portfolio_id)
        if portfolio.status not in self.TERMINAL_STATUSES:
            portfolio.status = "MULTI_CAMPAIGN_PAUSED"
            portfolio.current_campaign_id = ""
            self._checkpoint(portfolio, event="PORTFOLIO_PAUSED_MANUALLY")
            self.store.save(portfolio)
        return self._response(portfolio, success=True)

    def get_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        portfolio = self.store.get(portfolio_id)
        return portfolio.to_dict() if portfolio is not None else None

    def recent_portfolios(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.list_recent(limit=limit)

    def _execute(
        self,
        portfolio: MultiCampaignPortfolio,
        *,
        auto_approve: bool,
        auto_rollback: bool,
        final_validation: bool,
        continue_on_failure: bool,
        rollback_completed_on_failure: bool,
        max_campaigns_per_run: int | None,
    ) -> dict[str, Any]:
        safe_limit = self._safe_limit(max_campaigns_per_run)
        processed_now = 0
        portfolio.status = "MULTI_CAMPAIGN_RUNNING"
        self.store.save(portfolio)

        while True:
            blocked_now = self.scheduler.mark_blocked(portfolio)
            if blocked_now:
                self._checkpoint(
                    portfolio,
                    event="DEPENDENT_CAMPAIGNS_BLOCKED",
                    metadata={"campaign_ids": blocked_now},
                )
                self.store.save(portfolio)

            item = self.scheduler.next_campaign(portfolio)
            if item is None:
                break

            portfolio.current_campaign_id = item.campaign_id
            item.status = "RUNNING"
            item.attempt_count += 1
            item.started_at = item.started_at or self._now()
            self._checkpoint(
                portfolio,
                event="CAMPAIGN_STARTED",
                campaign_id=item.campaign_id,
            )
            self.store.save(portfolio)

            result = self._run_campaign(
                item,
                auto_approve=auto_approve,
                auto_rollback=auto_rollback,
                final_validation=final_validation,
            )
            item.result = dict(result)
            status = str(result.get("status", "UNKNOWN")).upper()
            processed_now += 1

            if bool(result.get("success", False)) and status in self.COMPLETED_STATUSES:
                item.status = "COMPLETED"
                item.completed_at = self._now()
                self._checkpoint(
                    portfolio,
                    event="CAMPAIGN_COMPLETED",
                    campaign_id=item.campaign_id,
                )
                self.store.save(portfolio)
            elif status in self.PAUSED_STATUSES:
                item.status = "PAUSED"
                portfolio.status = "MULTI_CAMPAIGN_PAUSED"
                portfolio.current_campaign_id = ""
                self._checkpoint(
                    portfolio,
                    event="CAMPAIGN_PAUSED",
                    campaign_id=item.campaign_id,
                )
                self.store.save(portfolio)
                return self._response(portfolio, success=True)
            else:
                item.status = "FAILED"
                if "ROLLED_BACK" in status:
                    item.warnings.append(
                        "Nieudana kampania została cofnięta przez własny workflow."
                    )
                item.completed_at = self._now()
                item.errors = [str(value) for value in result.get("errors", [])]
                portfolio.errors.extend(item.errors)
                self._checkpoint(
                    portfolio,
                    event="CAMPAIGN_FAILED",
                    campaign_id=item.campaign_id,
                )
                self.store.save(portfolio)

                if not continue_on_failure:
                    portfolio.status = "MULTI_CAMPAIGN_FAILED"
                    if auto_rollback and rollback_completed_on_failure:
                        return self._rollback_portfolio(
                            portfolio,
                            status_on_success="MULTI_CAMPAIGN_FAILED_AND_ROLLED_BACK",
                        )
                    return self._response(portfolio, success=False)

            if (
                safe_limit is not None
                and processed_now >= safe_limit
                and portfolio.pending_campaign_ids
            ):
                portfolio.status = "MULTI_CAMPAIGN_PAUSED"
                portfolio.current_campaign_id = ""
                self._checkpoint(portfolio, event="PORTFOLIO_PAUSED_LIMIT")
                self.store.save(portfolio)
                return self._response(portfolio, success=True)

        portfolio.current_campaign_id = ""
        if portfolio.failed_campaign_ids or portfolio.blocked_campaign_ids:
            portfolio.status = "MULTI_CAMPAIGN_PARTIAL_FAILURE"
            if auto_rollback and rollback_completed_on_failure and portfolio.completed_campaign_ids:
                return self._rollback_portfolio(
                    portfolio,
                    status_on_success="MULTI_CAMPAIGN_FAILED_AND_ROLLED_BACK",
                )
            self.store.save(portfolio)
            return self._response(portfolio, success=False)

        validation = (
            self._validate_project(portfolio)
            if final_validation
            else {"success": True, "status": "SKIPPED", "errors": []}
        )
        portfolio.final_validation = validation
        if not bool(validation.get("success", False)):
            portfolio.status = "MULTI_CAMPAIGN_FINAL_VALIDATION_FAILED"
            portfolio.errors.extend(str(item) for item in validation.get("errors", []))
            self._checkpoint(portfolio, event="PORTFOLIO_FINAL_VALIDATION_FAILED")
            self.store.save(portfolio)
            if auto_rollback:
                return self._rollback_portfolio(
                    portfolio,
                    status_on_success=(
                        "MULTI_CAMPAIGN_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK"
                    ),
                )
            return self._response(portfolio, success=False)

        portfolio.status = "MULTI_CAMPAIGN_COMPLETED"
        portfolio.completed_at = self._now()
        self._checkpoint(portfolio, event="PORTFOLIO_COMPLETED")
        self.store.save(portfolio)
        return self._response(portfolio, success=True)

    def _run_campaign(
        self,
        item: ManagedCampaign,
        *,
        auto_approve: bool,
        auto_rollback: bool,
        final_validation: bool,
    ) -> dict[str, Any]:
        options = dict(item.metadata.get("options", {}) or {})
        # An explicit approval supplied for the current resume must win over
        # a persisted False from the original plan. This keeps approval
        # scoped to one invocation without changing the stored policy.
        effective_auto_approve = bool(
            auto_approve
            or options.get("auto_approve", False)
        )
        effective_auto_rollback = bool(options.get("auto_rollback", auto_rollback))
        effective_validation = bool(options.get("final_validation", final_validation))
        max_stages = options.get("max_stages_per_run")
        existing = None
        if hasattr(self.campaign_workflow, "get_campaign"):
            existing = self.campaign_workflow.get_campaign(item.campaign_id)

        if existing:
            return self.campaign_workflow.resume(
                item.campaign_id,
                auto_approve=effective_auto_approve,
                auto_rollback=effective_auto_rollback,
                final_validation=effective_validation,
                max_stages_per_run=max_stages,
            )
        return self.campaign_workflow.run(
            item.objective,
            stages=item.stages,
            campaign_id=item.campaign_id,
            auto_execute=True,
            auto_approve=effective_auto_approve,
            auto_rollback=effective_auto_rollback,
            final_validation=effective_validation,
            max_stages_per_run=max_stages,
            metadata={
                "portfolio_id": item.metadata.get("portfolio_id", ""),
                "priority": item.priority,
            },
        )

    def _validate_project(self, portfolio: MultiCampaignPortfolio) -> dict[str, Any]:
        try:
            result = self.validator.run_test_suite(
                changed_files=list(
                    dict.fromkeys(
                        path
                        for item in portfolio.campaigns
                        for path in item.targets
                    )
                ),
                full_suite=True,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "MULTI_CAMPAIGN_VALIDATION_EXCEPTION",
                "errors": [f"{type(error).__name__}: {error}"],
                "traceback": traceback.format_exc(),
            }
        if hasattr(result, "as_dict"):
            value = result.as_dict()
        elif isinstance(result, dict):
            value = dict(result)
        else:
            value = {
                "success": False,
                "status": "MULTI_CAMPAIGN_VALIDATION_INVALID_RESULT",
                "errors": ["Walidator zwrócił nieprawidłowy wynik."],
            }
        value.setdefault(
            "status",
            "MULTI_CAMPAIGN_VALIDATION_PASSED"
            if value.get("success", False)
            else "MULTI_CAMPAIGN_VALIDATION_FAILED",
        )
        value.setdefault("errors", [])
        return value

    def _rollback_portfolio(
        self,
        portfolio: MultiCampaignPortfolio,
        *,
        status_on_success: str,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        success = True
        completed = self._completion_order(portfolio)
        for campaign_id in reversed(completed):
            try:
                result = self.campaign_workflow.rollback(campaign_id)
            except Exception as error:
                result = {
                    "success": False,
                    "status": "CAMPAIGN_ROLLBACK_EXCEPTION",
                    "errors": [f"{type(error).__name__}: {error}"],
                "traceback": traceback.format_exc(),
                }
            results.append({"campaign_id": campaign_id, "result": dict(result)})
            item = portfolio.campaign(campaign_id)
            if bool(result.get("success", False)):
                item.status = "ROLLED_BACK"
            else:
                success = False
                item.errors.extend(str(value) for value in result.get("errors", []))

        portfolio.rollback = {
            "success": success,
            "campaigns": results,
            "rolled_back_count": sum(
                1 for item in results if item["result"].get("success", False)
            ),
        }
        if success:
            portfolio.status = status_on_success
            portfolio.completed_at = self._now()
            self._checkpoint(portfolio, event="PORTFOLIO_ROLLED_BACK")
        else:
            portfolio.status = "MULTI_CAMPAIGN_ROLLBACK_FAILED"
            self._checkpoint(portfolio, event="PORTFOLIO_ROLLBACK_FAILED")
        self.store.save(portfolio)
        return self._response(
            portfolio,
            success=(success and status_on_success == "MULTI_CAMPAIGN_ROLLED_BACK"),
        )

    def _checkpoint(
        self,
        portfolio: MultiCampaignPortfolio,
        *,
        event: str,
        campaign_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        portfolio.checkpoints.append(
            {
                "checkpoint_id": f"portfolio-checkpoint-{uuid4().hex}",
                "timestamp": self._now(),
                "event": str(event),
                "campaign_id": str(campaign_id),
                "portfolio_status": portfolio.status,
                "completed_campaign_ids": list(portfolio.completed_campaign_ids),
                "pending_campaign_ids": list(portfolio.pending_campaign_ids),
                "metadata": dict(metadata or {}),
            }
        )
        if len(portfolio.checkpoints) > 300:
            portfolio.checkpoints = portfolio.checkpoints[-300:]

    def _response(
        self,
        portfolio: MultiCampaignPortfolio,
        *,
        success: bool,
    ) -> dict[str, Any]:
        checkpoint = dict(portfolio.checkpoints[-1]) if portfolio.checkpoints else {}
        return {
            "success": bool(success),
            "status": portfolio.status,
            "operation": "multi_campaign",
            "portfolio_id": portfolio.portfolio_id,
            "portfolio": portfolio.to_dict(),
            "checkpoint": checkpoint,
            "campaigns_count": len(portfolio.campaigns),
            "completed_campaigns": len(portfolio.completed_campaign_ids),
            "failed_campaigns": len(portfolio.failed_campaign_ids),
            "blocked_campaigns": len(portfolio.blocked_campaign_ids),
            "final_validation": dict(portfolio.final_validation),
            "rollback": dict(portfolio.rollback),
            "report_path": str(self.store.path),
            "errors": list(portfolio.errors),
        }

    @staticmethod
    def _completion_order(
        portfolio: MultiCampaignPortfolio,
    ) -> list[str]:
        completed_ids = set(portfolio.completed_campaign_ids)
        order: list[str] = []
        for checkpoint in portfolio.checkpoints:
            if checkpoint.get("event") != "CAMPAIGN_COMPLETED":
                continue
            campaign_id = str(checkpoint.get("campaign_id", ""))
            if campaign_id in completed_ids and campaign_id not in order:
                order.append(campaign_id)
        for campaign_id in portfolio.execution_order:
            if campaign_id in completed_ids and campaign_id not in order:
                order.append(campaign_id)
        return order

    @staticmethod
    def _safe_limit(value: int | None) -> int | None:
        if value is None:
            return None
        limit = int(value)
        if limit <= 0:
            raise ValueError("max_campaigns_per_run musi być większe od zera.")
        return min(30, limit)

    @staticmethod
    def _override(value: bool | None, default: Any) -> bool:
        return bool(default) if value is None else bool(value)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _not_found(portfolio_id: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "MULTI_CAMPAIGN_NOT_FOUND",
            "portfolio_id": str(portfolio_id),
            "portfolio": {},
            "errors": ["Nie znaleziono portfolio kampanii."],
        }

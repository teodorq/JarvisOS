from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .multi_campaign_workflow import MultiCampaignWorkflow
from .portfolio_director_store import PortfolioDirectorStore
from .portfolio_optimizer import PortfolioOptimizer


class AutonomousCampaignDirector:
    """Continuously re-optimizes and directs a campaign portfolio."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        workflow: MultiCampaignWorkflow | Any,
        optimizer: PortfolioOptimizer | None = None,
        store: PortfolioDirectorStore | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.workflow = workflow
        self.optimizer = optimizer or PortfolioOptimizer(
            self.project_root,
            store=workflow.store,
        )
        self.store = store or PortfolioDirectorStore(self.project_root)

    def optimize(
        self,
        portfolio_id: str,
        *,
        constraints: dict[str, Any] | None = None,
        apply: bool = True,
    ) -> dict[str, Any]:
        portfolio = self.workflow.store.get(portfolio_id)
        if portfolio is None:
            return self.workflow._not_found(portfolio_id)
        optimization = self.optimizer.optimize(
            portfolio,
            constraints=constraints,
            apply=apply,
        )
        if apply:
            self._checkpoint(
                portfolio,
                event="PORTFOLIO_OPTIMIZED",
                metadata={
                    "selected_campaign_ids": optimization["selected_campaign_ids"],
                    "average_score": optimization["average_score"],
                },
            )
            self.workflow.store.save(portfolio)
        response = self.workflow._response(portfolio, success=True)
        response["status"] = "PORTFOLIO_OPTIMIZED"
        response["optimization"] = optimization
        response["director_run"] = {}
        return response

    def direct(
        self,
        portfolio_id: str,
        *,
        constraints: dict[str, Any] | None = None,
        auto_approve: bool | None = None,
        auto_rollback: bool | None = None,
        final_validation: bool | None = None,
        max_cycles: int = 30,
        max_retries_per_campaign: int = 1,
        max_failures: int = 2,
        rollback_on_stop: bool = False,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        portfolio = self.workflow.store.get(portfolio_id)
        if portfolio is None:
            return self.workflow._not_found(portfolio_id)

        recovered_campaign_ids = self._recover_interrupted_campaigns(
            portfolio
        )
        if recovered_campaign_ids:
            self._checkpoint(
                portfolio,
                event="DIRECTOR_INTERRUPTED_CAMPAIGNS_RECOVERED",
                metadata={
                    "campaign_ids": recovered_campaign_ids,
                },
            )
            self.workflow.store.save(portfolio)

        run_id = f"director-{uuid4().hex}"
        policy = {
            "max_cycles": min(100, max(1, int(max_cycles))),
            "max_retries_per_campaign": min(
                5,
                max(0, int(max_retries_per_campaign)),
            ),
            "max_failures": min(30, max(1, int(max_failures))),
            "rollback_on_stop": bool(rollback_on_stop),
            "constraints": dict(constraints or {}),
        }
        run = {
            "run_id": run_id,
            "portfolio_id": portfolio_id,
            "status": "CAMPAIGN_DIRECTOR_RUNNING",
            "started_at": self._now(),
            "completed_at": "",
            "cycles": 0,
            "failures": 0,
            "retries": 0,
            "policy": policy,
            "decisions": [],
            "last_optimization": {},
            "errors": [],
        }
        self.store.save(run)
        self._notify(
            progress_callback,
            "DIRECTOR_STARTED",
            run=run,
            portfolio=portfolio,
        )

        for cycle in range(1, policy["max_cycles"] + 1):
            portfolio = self.workflow.store.get(portfolio_id)
            if portfolio is None:
                return self._finish(
                    run,
                    status="CAMPAIGN_DIRECTOR_PORTFOLIO_LOST",
                    success=False,
                    errors=["Portfolio zniknęło podczas pracy dyrektora."],
                )

            if portfolio.status in self.workflow.TERMINAL_STATUSES:
                success = portfolio.status == "MULTI_CAMPAIGN_COMPLETED"
                return self._finish(
                    run,
                    status=portfolio.status,
                    success=success,
                    portfolio=portfolio,
                )

            optimization = self.optimizer.optimize(
                portfolio,
                constraints=policy["constraints"],
                apply=True,
            )
            run["cycles"] = cycle
            run["last_optimization"] = optimization
            selected = list(optimization["selected_campaign_ids"])
            decision = {
                "cycle": cycle,
                "timestamp": self._now(),
                "selected_campaign_id": selected[0] if selected else "",
                "optimized_order": list(optimization["optimized_order"]),
                "average_score": optimization["average_score"],
                "deferred_campaigns": list(optimization["deferred_campaigns"]),
            }
            run["decisions"].append(decision)
            self._checkpoint(
                portfolio,
                event="DIRECTOR_CYCLE_OPTIMIZED",
                metadata={
                    "run_id": run_id,
                    "cycle": cycle,
                    "selected_campaign_id": decision["selected_campaign_id"],
                },
            )
            self.workflow.store.save(portfolio)
            self.store.save(run)
            self._notify(
                progress_callback,
                "DIRECTOR_CYCLE_OPTIMIZED",
                run=run,
                portfolio=portfolio,
                metadata={
                    "cycle": cycle,
                    "selected_campaign_id": (
                        decision["selected_campaign_id"]
                    ),
                },
            )

            if not selected:
                if not portfolio.pending_campaign_ids:
                    result = self.workflow.resume(
                        portfolio_id,
                        auto_approve=auto_approve,
                        auto_rollback=auto_rollback,
                        final_validation=final_validation,
                        continue_on_failure=True,
                        rollback_completed_on_failure=False,
                        max_campaigns_per_run=1,
                    )
                    portfolio = self.workflow.store.get(portfolio_id) or portfolio
                    terminal = str(result.get("status", "UNKNOWN"))
                    return self._finish(
                        run,
                        status=terminal,
                        success=bool(result.get("success", False)),
                        portfolio=portfolio,
                    )

                blockers = self._failed_dependency_blockers(
                    portfolio
                )

                if blockers:
                    portfolio.status = (
                        "CAMPAIGN_DIRECTOR_BLOCKED_BY_"
                        "FAILED_DEPENDENCY"
                    )
                    portfolio.current_campaign_id = ""
                    self._checkpoint(
                        portfolio,
                        event=(
                            "DIRECTOR_BLOCKED_BY_"
                            "FAILED_DEPENDENCY"
                        ),
                        metadata={
                            "run_id": run_id,
                            "blockers": blockers,
                        },
                    )
                    self.workflow.store.save(
                        portfolio
                    )
                    return self._finish(
                        run,
                        status=portfolio.status,
                        success=False,
                        portfolio=portfolio,
                        errors=[
                            "Kampanie oczekujące zależą od "
                            "nieudanej kampanii: "
                            + ", ".join(blockers),
                        ],
                    )

                portfolio.status = "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS"
                portfolio.current_campaign_id = ""
                self._checkpoint(
                    portfolio,
                    event="DIRECTOR_PAUSED_CONSTRAINTS",
                    metadata={"run_id": run_id},
                )
                self.workflow.store.save(portfolio)
                return self._finish(
                    run,
                    status=portfolio.status,
                    success=True,
                    portfolio=portfolio,
                )

            before_attempts = {
                item.campaign_id: item.attempt_count
                for item in portfolio.campaigns
            }
            result = self.workflow.resume(
                portfolio_id,
                auto_approve=auto_approve,
                auto_rollback=auto_rollback,
                final_validation=final_validation,
                continue_on_failure=True,
                rollback_completed_on_failure=False,
                max_campaigns_per_run=1,
            )
            portfolio = self.workflow.store.get(portfolio_id) or portfolio
            decision["workflow_status"] = str(result.get("status", "UNKNOWN"))
            decision["success"] = bool(result.get("success", False))
            self._notify(
                progress_callback,
                "DIRECTOR_CAMPAIGN_FINISHED",
                run=run,
                portfolio=portfolio,
                metadata={
                    "cycle": cycle,
                    "workflow_status": decision["workflow_status"],
                    "success": decision["success"],
                },
            )
            failed_now = self._new_failed_campaigns(portfolio, before_attempts)

            for item in failed_now:
                run["failures"] += 1
                retries = int(item.metadata.get("director_retry_count", 0) or 0)
                if retries < policy["max_retries_per_campaign"]:
                    item.metadata["director_retry_count"] = retries + 1
                    item.metadata["estimated_risk"] = min(
                        10.0,
                        float(item.metadata.get("estimated_risk", 5.0) or 5.0) + 0.5,
                    )
                    item.status = "PENDING"
                    item.completed_at = ""
                    item.warnings.append(
                        "Dyrektor zaplanował autonomiczną ponowną próbę po błędzie."
                    )
                    run["retries"] += 1
                    decision.setdefault("retry_campaign_ids", []).append(item.campaign_id)
                    self._checkpoint(
                        portfolio,
                        event="DIRECTOR_RETRY_SCHEDULED",
                        campaign_id=item.campaign_id,
                        metadata={"run_id": run_id, "cycle": cycle},
                    )
                    self._notify(
                        progress_callback,
                        "DIRECTOR_RETRY_SCHEDULED",
                        run=run,
                        portfolio=portfolio,
                        metadata={
                            "cycle": cycle,
                            "campaign_id": item.campaign_id,
                        },
                    )

            self._recover_blocked_dependents(portfolio)
            self.workflow.store.save(portfolio)
            self.store.save(run)

            if run["failures"] >= policy["max_failures"]:
                if policy["rollback_on_stop"] and portfolio.completed_campaign_ids:
                    rollback = self.workflow.rollback(portfolio_id)
                    portfolio = self.workflow.store.get(portfolio_id) or portfolio
                    run["rollback"] = rollback
                    return self._finish(
                        run,
                        status="CAMPAIGN_DIRECTOR_STOPPED_AND_ROLLED_BACK",
                        success=bool(rollback.get("success", False)),
                        portfolio=portfolio,
                    )
                portfolio.status = "CAMPAIGN_DIRECTOR_STOPPED_FAILURE_LIMIT"
                portfolio.current_campaign_id = ""
                self._checkpoint(
                    portfolio,
                    event="DIRECTOR_FAILURE_LIMIT_REACHED",
                    metadata={"run_id": run_id},
                )
                self.workflow.store.save(portfolio)
                return self._finish(
                    run,
                    status=portfolio.status,
                    success=False,
                    portfolio=portfolio,
                )

            if portfolio.status in self.workflow.TERMINAL_STATUSES:
                return self._finish(
                    run,
                    status=portfolio.status,
                    success=portfolio.status == "MULTI_CAMPAIGN_COMPLETED",
                    portfolio=portfolio,
                )

        portfolio = self.workflow.store.get(portfolio_id)
        if portfolio is not None:
            portfolio.status = "CAMPAIGN_DIRECTOR_PAUSED_CYCLE_LIMIT"
            portfolio.current_campaign_id = ""
            self._checkpoint(
                portfolio,
                event="DIRECTOR_CYCLE_LIMIT_REACHED",
                metadata={"run_id": run_id},
            )
            self.workflow.store.save(portfolio)
        return self._finish(
            run,
            status="CAMPAIGN_DIRECTOR_PAUSED_CYCLE_LIMIT",
            success=True,
            portfolio=portfolio,
        )

    def status(
        self,
        *,
        run_id: str = "",
        portfolio_id: str = "",
    ) -> dict[str, Any]:
        run = self.store.get(run_id) if run_id else self.store.latest_for_portfolio(portfolio_id)
        if run is None:
            return {
                "success": False,
                "status": "CAMPAIGN_DIRECTOR_RUN_NOT_FOUND",
                "operation": "multi_campaign",
                "portfolio_id": str(portfolio_id),
                "portfolio": {},
                "director_run": {},
                "errors": ["Nie znaleziono przebiegu dyrektora kampanii."],
            }
        portfolio = self.workflow.store.get(str(run.get("portfolio_id", "")))
        return {
            "success": True,
            "status": str(run.get("status", "UNKNOWN")),
            "operation": "multi_campaign",
            "portfolio_id": str(run.get("portfolio_id", "")),
            "portfolio": portfolio.to_dict() if portfolio is not None else {},
            "director_run": run,
            "optimization": dict(run.get("last_optimization", {}) or {}),
            "errors": list(run.get("errors", [])),
            "report_path": str(self.store.path),
        }

    def recent(self, *, limit: int = 20) -> dict[str, Any]:
        runs = self.store.list_recent(limit=limit)
        return {
            "success": True,
            "status": "CAMPAIGN_DIRECTOR_RECENT",
            "operation": "multi_campaign",
            "portfolio_id": "",
            "portfolio": {},
            "director_run": {},
            "director_runs": runs,
            "errors": [],
            "report_path": str(self.store.path),
        }

    def _finish(
        self,
        run: dict[str, Any],
        *,
        status: str,
        success: bool,
        portfolio: Any | None = None,
        errors: list[str] | None = None,
    ) -> dict[str, Any]:
        run["status"] = str(status)
        run["completed_at"] = self._now()
        if errors:
            run["errors"].extend(str(value) for value in errors)
        saved = self.store.save(run)
        portfolio_dict = portfolio.to_dict() if portfolio is not None else {}
        return {
            "success": bool(success),
            "status": str(status),
            "operation": "multi_campaign",
            "portfolio_id": str(run.get("portfolio_id", "")),
            "portfolio": portfolio_dict,
            "director_run": saved,
            "optimization": dict(run.get("last_optimization", {}) or {}),
            "campaigns_count": len(portfolio_dict.get("campaigns", [])),
            "completed_campaigns": len(portfolio_dict.get("completed_campaign_ids", [])),
            "failed_campaigns": len(portfolio_dict.get("failed_campaign_ids", [])),
            "blocked_campaigns": len(portfolio_dict.get("blocked_campaign_ids", [])),
            "errors": list(run.get("errors", [])),
            "report_path": str(self.store.path),
        }

    @staticmethod
    def _recover_interrupted_campaigns(
        portfolio: Any,
    ) -> list[str]:
        """Make interrupted managed campaigns eligible before optimization."""
        recovered: list[str] = []

        for item in portfolio.campaigns:
            if str(item.status).upper() != "RUNNING":
                continue

            nested_status = str(
                dict(item.result or {})
                .get("campaign", {})
                .get("status", "")
                if isinstance(
                    dict(item.result or {}).get("campaign", {}),
                    dict,
                )
                else ""
            ).upper()
            item.status = (
                "PAUSED"
                if nested_status in {
                    "CAMPAIGN_PREVIEW_READY",
                    "CAMPAIGN_PAUSED",
                    "CAMPAIGN_PLAN_READY",
                }
                else "PENDING"
            )
            item.warnings.append(
                "Dyrektor odzyskał kampanię przerwaną przed "
                "optymalizacją i przywrócił ją do kolejki."
            )
            recovered.append(item.campaign_id)

        if recovered:
            portfolio.current_campaign_id = ""
            portfolio.warnings.append(
                "Odzyskano przerwane kampanie przed cyklem dyrektora."
            )

        return recovered

    @staticmethod
    def _failed_dependency_blockers(
        portfolio: Any,
    ) -> list[str]:
        by_id = {
            item.campaign_id: item
            for item in portfolio.campaigns
        }
        failed_states = {
            "FAILED",
            "ROLLED_BACK",
            "CANCELLED",
            "BLOCKED",
        }
        blockers: list[str] = []

        for item in portfolio.campaigns:
            if item.status not in {
                "PENDING",
                "PAUSED",
                "BLOCKED",
            }:
                continue

            for dependency in item.depends_on:
                dependency_item = by_id.get(
                    dependency
                )

                if (
                    dependency_item is not None
                    and dependency_item.status
                    in failed_states
                    and dependency not in blockers
                ):
                    blockers.append(dependency)

        return blockers

    @staticmethod
    def _recover_blocked_dependents(portfolio: Any) -> None:
        by_id = {item.campaign_id: item for item in portfolio.campaigns}
        failure_states = {"FAILED", "ROLLED_BACK", "CANCELLED", "BLOCKED"}
        changed = True
        while changed:
            changed = False
            for item in portfolio.campaigns:
                if item.status != "BLOCKED":
                    continue
                if any(
                    by_id[dependency].status in failure_states
                    for dependency in item.depends_on
                ):
                    continue
                item.status = "PENDING"
                item.warnings.append(
                    "Dyrektor odblokował kampanię po zaplanowaniu retry zależności."
                )
                changed = True

    @staticmethod
    def _new_failed_campaigns(portfolio: Any, before_attempts: dict[str, int]) -> list[Any]:
        return [
            item
            for item in portfolio.campaigns
            if item.status == "FAILED"
            and item.attempt_count > before_attempts.get(item.campaign_id, 0)
        ]

    def _checkpoint(
        self,
        portfolio: Any,
        *,
        event: str,
        campaign_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if hasattr(self.workflow, "_checkpoint"):
            self.workflow._checkpoint(
                portfolio,
                event=event,
                campaign_id=campaign_id,
                metadata=metadata,
            )

    @staticmethod
    def _notify(
        callback: Any | None,
        event: str,
        *,
        run: dict[str, Any],
        portfolio: Any | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not callable(callback):
            return

        try:
            callback(
                str(event),
                {
                    "director_run": dict(run),
                    "portfolio": (
                        portfolio.to_dict()
                        if hasattr(portfolio, "to_dict")
                        else dict(portfolio)
                        if isinstance(portfolio, dict)
                        else {}
                    ),
                    "metadata": dict(metadata or {}),
                },
            )
        except Exception:
            return

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

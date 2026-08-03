from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import traceback
from typing import Any

from .project_intelligence_models import TERMINAL_OPPORTUNITY_STATES
from .project_intelligence_service import (
    ProjectIntelligenceService,
    bootstrap_project_intelligence,
)
from .self_directed_development_service import (
    SelfDirectedDevelopmentService,
    bootstrap_self_directed_development,
)
from .strategic_development_service import (
    StrategicDevelopmentService,
    bootstrap_strategic_development,
)
from .strategic_execution_models import (
    ACTIVE_STRATEGIC_EXECUTION_STATES,
    TERMINAL_STRATEGIC_EXECUTION_STATES,
    StrategicExecutionRecord,
)
from .strategic_execution_store import StrategicExecutionStore


class StrategicExecutionService:
    """B58 persistent strategic goal execution and outcome learning."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        project_intelligence: ProjectIntelligenceService | Any,
        self_directed: SelfDirectedDevelopmentService | Any,
        strategic_development: StrategicDevelopmentService | Any,
        store: StrategicExecutionStore | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.project_intelligence = project_intelligence
        self.self_directed = self_directed
        self.strategic_development = strategic_development
        self.store = store or StrategicExecutionStore(self.project_root)
        self._lock = threading.RLock()

    def dispatch_next(self) -> dict[str, Any]:
        with self._lock:
            runtime = self.store.runtime()
            policy = self.store.policy()
            if not bool(runtime.get("enabled", True)) or not bool(
                policy.get("enabled", True)
            ):
                return self._response(
                    "STRATEGIC_EXECUTION_DISABLED",
                    success=True,
                )
            if bool(runtime.get("paused", False)):
                return self._response(
                    "STRATEGIC_EXECUTION_PAUSED",
                    success=True,
                )
            if not bool(policy.get("integrate_with_b57", True)):
                return self._response(
                    "STRATEGIC_EXECUTION_B57_INTEGRATION_DISABLED",
                    success=True,
                )
            if not bool(self.strategic_development.is_enabled()):
                return self._response(
                    "STRATEGIC_EXECUTION_STRATEGY_NOT_RUNNING",
                    success=True,
                )

            self.reconcile(refresh_roadmap=False)
            active = self.store.active_records()
            if active:
                first = active[0]
                return self._response(
                    "STRATEGIC_EXECUTION_WAITING_FOR_ACTIVE_JOB",
                    success=True,
                    execution=first,
                    job_id=str(first.get("job_id", "")),
                )

            self.store.update_runtime({
                "phase": "SELECTING",
                "last_error": "",
            })
            recommendation = self._strategic_recommendation()
            goal = self._mapping(recommendation.get("selected"))
            opportunity = self._mapping(
                recommendation.get("recommendation")
            )
            goal_id = str(goal.get("goal_id", "")).strip()
            opportunity_id = str(
                opportunity.get("opportunity_id", "")
            ).strip()
            if not goal_id or not opportunity_id:
                return self._finish_cycle(
                    "STRATEGIC_EXECUTION_NO_SAFE_RECOMMENDATION",
                    success=True,
                    phase="IDLE",
                    recommendation=recommendation,
                )

            self.store.update_runtime({"phase": "DISPATCHING"})
            dispatched = self.project_intelligence.dispatch_opportunity(
                opportunity_id,
                force=True,
            )
            job_id = str(dispatched.get("job_id", "")).strip()
            if not bool(dispatched.get("success", False)) or not job_id:
                errors = list(dispatched.get("errors", []))
                return self._finish_cycle(
                    "STRATEGIC_EXECUTION_DISPATCH_FAILED",
                    success=False,
                    phase="DISPATCH_FAILED",
                    errors=errors,
                    recommendation=recommendation,
                    dispatch=dispatched,
                )

            record = StrategicExecutionRecord(
                goal_id=goal_id,
                opportunity_id=opportunity_id,
                job_id=job_id,
                status="DISPATCHED",
                target=str(opportunity.get("target", "")),
                objective=str(opportunity.get("objective", "")),
                metadata={
                    "source": "B58StrategicExecution",
                    "goal_title": str(goal.get("title", "")),
                    "subsystem": str(goal.get("subsystem", "")),
                    "issue_type": str(goal.get("issue_type", "")),
                    "strategic_status": str(
                        recommendation.get("status", "")
                    ),
                    **self._autonomy_governance_metadata(),
                },
            )
            saved = self.store.save_record(record)
            self._enrich_dispatch(saved)
            self._refresh_roadmap_best_effort(goal_id)
            result = self._finish_cycle(
                "STRATEGIC_EXECUTION_JOB_DISPATCHED",
                success=True,
                phase="WAITING_FOR_JOB",
                execution=saved,
                recommendation=recommendation,
                dispatch=dispatched,
                job_id=job_id,
                strategic_goal=goal,
                strategic_status=recommendation.get("status", ""),
                active_execution_id=saved.get("execution_id", ""),
                active_job_id=job_id,
                active_goal_id=goal_id,
                last_opportunity_id=opportunity_id,
            )
            return result

    def reconcile(
        self,
        *,
        refresh_roadmap: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            self.store.update_runtime({
                "phase": "RECONCILING",
                "last_error": "",
            })
            recovered = self._recover_records()
            changed: list[dict[str, Any]] = []
            try:
                for record in self.store.list_records(limit=10000):
                    if str(record.get("status", "")).upper() in (
                        TERMINAL_STRATEGIC_EXECUTION_STATES
                    ):
                        continue
                    state, category, error = self._current_state(record)
                    if not state:
                        continue
                    previous = str(record.get("status", "")).upper()
                    if state in TERMINAL_STRATEGIC_EXECUTION_STATES:
                        changed.append(
                            self._apply_outcome(
                                record,
                                state,
                                category=category,
                                error=error,
                                refresh_roadmap=False,
                            )
                        )
                    elif state != previous:
                        record["status"] = state
                        record["outcome_category"] = category
                        record["last_error"] = error
                        saved = self.store.save_record(record)
                        changed.append(saved)
                        self._record_history(
                            "STRATEGIC_EXECUTION_STATE_CHANGED",
                            success=True,
                            record=saved,
                            outcome=state,
                        )
                        if state == "WAITING_APPROVAL":
                            runtime = self.store.runtime()
                            self.store.update_runtime({
                                "waiting_approval_total": int(
                                    runtime.get(
                                        "waiting_approval_total", 0
                                    )
                                ) + 1,
                            })
                if changed and refresh_roadmap:
                    self._refresh_roadmap_best_effort("")
                active = self.store.active_records()
                first = active[0] if active else {}
                runtime = self.store.runtime()
                self.store.update_runtime({
                    "phase": (
                        "WAITING_APPROVAL"
                        if str(first.get("status", "")).upper()
                        == "WAITING_APPROVAL"
                        else "WAITING_FOR_JOB"
                        if first
                        else "READY"
                    ),
                    "cycles_completed": int(
                        runtime.get("cycles_completed", 0)
                    ) + 1,
                    "active_execution_id": str(
                        first.get("execution_id", "")
                    ),
                    "active_job_id": str(first.get("job_id", "")),
                    "active_goal_id": str(first.get("goal_id", "")),
                    "last_error": "",
                })
                return self._response(
                    "STRATEGIC_EXECUTION_RECONCILED",
                    success=True,
                    changed=changed,
                    recovered=recovered,
                    active=active,
                )
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                self.store.update_runtime({
                    "phase": "FAILED",
                    "last_error": message,
                })
                return self._response(
                    "STRATEGIC_EXECUTION_RECONCILE_FAILED",
                    success=False,
                    errors=[message],
                    traceback=traceback.format_exc()[-12000:],
                )

    def observe_outcome(
        self,
        opportunity: dict[str, Any],
        outcome_status: str,
    ) -> dict[str, Any]:
        with self._lock:
            item = dict(opportunity or {})
            job_id = str(item.get("job_id", "")).strip()
            opportunity_id = str(
                item.get("opportunity_id", "")
            ).strip()
            record = self.store.find_by_job(job_id)
            if record is None:
                record = self.store.find_by_opportunity(opportunity_id)
            if record is None:
                return self._response(
                    "STRATEGIC_EXECUTION_OUTCOME_NOT_BOUND",
                    success=True,
                    opportunity=item,
                )
            state = self._normalize_outcome(
                outcome_status,
                opportunity=item,
                job=self._job(job_id),
            )
            category = (
                "CONSTRAINTS_PAUSE"
                if state == "DEFERRED_CONSTRAINTS"
                else str(item.get("diagnostic_category", "")).upper()
            )
            saved = self._apply_outcome(
                record,
                state,
                category=category,
                error=str(item.get("last_error", "")),
            )
            return self._response(
                "STRATEGIC_EXECUTION_OUTCOME_OBSERVED",
                success=state in {"COMPLETED", "DEFERRED_CONSTRAINTS"},
                execution=saved,
                outcome=state,
            )

    def start(self) -> dict[str, Any]:
        policy = self.store.update_policy({
            "enabled": True,
            "max_active_executions": 1,
            "auto_approve": False,
        })
        runtime = self.store.update_runtime({
            "enabled": True,
            "paused": False,
            "phase": "STARTING",
            "last_error": "",
        })
        strategic = self.strategic_development.start_background()
        self.reconcile()
        return self._response(
            "STRATEGIC_EXECUTION_STARTED",
            success=bool(strategic.get("success", False)),
            runtime=runtime,
            policy=policy,
            strategic=strategic,
        )

    def stop(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({
            "enabled": False,
            "paused": False,
            "phase": "STOPPED",
        })
        return self._response(
            "STRATEGIC_EXECUTION_STOPPED",
            success=True,
            runtime=runtime,
        )

    def pause(self) -> dict[str, Any]:
        strategic = self.strategic_development.pause()
        runtime = self.store.update_runtime({
            "paused": True,
            "phase": "PAUSED",
        })
        return self._response(
            "STRATEGIC_EXECUTION_PAUSED",
            success=True,
            runtime=runtime,
            strategic=strategic,
        )

    def resume(self) -> dict[str, Any]:
        self.store.update_policy({"enabled": True, "auto_approve": False})
        runtime = self.store.update_runtime({
            "enabled": True,
            "paused": False,
            "phase": "RESUMING",
        })
        strategic = self.strategic_development.resume()
        self.reconcile()
        return self._response(
            "STRATEGIC_EXECUTION_RESUMED",
            success=bool(strategic.get("success", False)),
            runtime=runtime,
            strategic=strategic,
        )

    def status(self) -> dict[str, Any]:
        self.reconcile()
        active = self.store.active_records()
        return self._response(
            "STRATEGIC_EXECUTION_STATUS",
            success=True,
            active=active,
            executions=self.store.list_records(limit=20),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_EXECUTION_HISTORY",
            success=True,
            history=self.store.history(limit=limit),
        )

    def update_policy(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        policy = self.store.update_policy({
            **dict(updates),
            "max_active_executions": 1,
            "auto_approve": False,
        })
        return self._response(
            "STRATEGIC_EXECUTION_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def is_enabled(self) -> bool:
        runtime = self.store.runtime()
        policy = self.store.policy()
        return bool(
            runtime.get("enabled", True)
            and not runtime.get("paused", False)
            and policy.get("enabled", True)
            and policy.get("integrate_with_b57", True)
            and policy.get("integrate_with_b56", True)
            and self.strategic_development.is_enabled()
        )

    def _apply_outcome(
        self,
        record: dict[str, Any],
        state: str,
        *,
        category: str = "",
        error: str = "",
        refresh_roadmap: bool = True,
    ) -> dict[str, Any]:
        normalized = self._normalize_outcome(state)
        previous = str(record.get("status", "")).upper()
        if previous in TERMINAL_STRATEGIC_EXECUTION_STATES:
            return dict(record)
        now = self._now()
        record.update({
            "status": normalized,
            "outcome_category": str(category).upper(),
            "last_error": str(error),
            "observed_at": now,
            "completed_at": now,
        })
        saved = self.store.save_record(record)
        runtime = self.store.runtime()
        completed = normalized == "COMPLETED"
        deferred = normalized == "DEFERRED_CONSTRAINTS"
        failed = normalized in {"FAILED", "CANCELLED", "REJECTED"}
        outcome = {
            "execution_id": saved.get("execution_id", ""),
            "goal_id": saved.get("goal_id", ""),
            "opportunity_id": saved.get("opportunity_id", ""),
            "job_id": saved.get("job_id", ""),
            "status": normalized,
            "category": str(category).upper(),
            "error": str(error),
            "observed_at": now,
        }
        self.store.update_runtime({
            "phase": "LEARNING",
            "active_execution_id": "",
            "active_job_id": "",
            "active_goal_id": "",
            "last_outcome": outcome,
            "completed_total": int(runtime.get("completed_total", 0))
            + int(completed),
            "failed_total": int(runtime.get("failed_total", 0))
            + int(failed),
            "deferred_total": int(runtime.get("deferred_total", 0))
            + int(deferred),
            "last_error": str(error) if failed else "",
        })
        self._record_history(
            "STRATEGIC_EXECUTION_OUTCOME_OBSERVED",
            success=completed or deferred,
            record=saved,
            outcome=normalized,
            error=error,
        )
        if refresh_roadmap:
            self._refresh_roadmap_best_effort(
                str(saved.get("goal_id", ""))
            )
        self._notify_strategic_portfolio(saved)
        return saved

    def _current_state(
        self,
        record: dict[str, Any],
    ) -> tuple[str, str, str]:
        opportunity = self.project_intelligence.store.get_opportunity(
            str(record.get("opportunity_id", ""))
        )
        job = self._job(str(record.get("job_id", "")))
        if isinstance(opportunity, dict):
            opportunity_state = str(
                opportunity.get("status", "")
            ).upper()
            if opportunity_state in TERMINAL_OPPORTUNITY_STATES:
                state = self._normalize_outcome(
                    opportunity_state,
                    opportunity=opportunity,
                    job=job,
                )
                return (
                    state,
                    self._diagnostic_category(job),
                    str(opportunity.get("last_error", "")),
                )
        if isinstance(job, dict):
            state = str(job.get("state", "")).upper()
            if state:
                normalized = self._normalize_outcome(
                    state,
                    opportunity=opportunity or {},
                    job=job,
                )
                return (
                    normalized,
                    self._diagnostic_category(job),
                    str(job.get("last_error", "")),
                )
        if isinstance(opportunity, dict):
            return (
                str(opportunity.get("status", "")).upper(),
                "",
                str(opportunity.get("last_error", "")),
            )
        return "", "", ""

    def _normalize_outcome(
        self,
        value: Any,
        *,
        opportunity: dict[str, Any] | None = None,
        job: dict[str, Any] | None = None,
    ) -> str:
        state = str(value or "UNKNOWN").upper()
        if self._is_constraints_deferral(job):
            return "DEFERRED_CONSTRAINTS"
        if state == "DEFERRED_CONSTRAINTS":
            return state
        if state in {
            "DISPATCHED",
            "QUEUED",
            "SCHEDULED",
            "WAITING_RESOURCES",
            "WAITING_APPROVAL",
            "RECOVERING",
            "RUNNING",
            "PAUSED",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "REJECTED",
        }:
            return state
        if state == "SUCCESS":
            return "COMPLETED"
        return state

    def _enrich_dispatch(self, record: dict[str, Any]) -> None:
        execution_id = str(record.get("execution_id", ""))
        goal_id = str(record.get("goal_id", ""))
        opportunity_id = str(record.get("opportunity_id", ""))
        job_id = str(record.get("job_id", ""))
        opportunity = self.project_intelligence.store.get_opportunity(
            opportunity_id
        )
        if isinstance(opportunity, dict):
            metadata = dict(opportunity.get("metadata", {}) or {})
            metadata.update({
                "strategic_execution_id": execution_id,
                "strategic_goal_id": goal_id,
                "strategic_source": "B58StrategicExecution",
            })
            self.project_intelligence.store.update_opportunity(
                opportunity_id,
                {"metadata": metadata},
            )
        job = self._job(job_id)
        long_store = self._long_running_store()
        if isinstance(job, dict) and long_store is not None:
            metadata = dict(job.get("metadata", {}) or {})
            metadata.update({
                "strategic_execution_id": execution_id,
                "strategic_goal_id": goal_id,
                "strategic_opportunity_id": opportunity_id,
                "strategic_source": "B58StrategicExecution",
            })
            execution_context = dict(
                job.get("execution_context", {}) or {}
            )
            context_metadata = dict(
                execution_context.get("metadata", {}) or {}
            )
            context_metadata.update(metadata)
            execution_context["metadata"] = context_metadata
            job["metadata"] = metadata
            job["execution_context"] = execution_context
            long_store.save_job(job)

    def _recover_records(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        long_store = self._long_running_store()
        if long_store is None:
            return recovered
        for job in long_store.list_jobs(limit=10000):
            metadata = dict(job.get("metadata", {}) or {})
            execution_id = str(
                metadata.get("strategic_execution_id", "")
            ).strip()
            goal_id = str(metadata.get("strategic_goal_id", "")).strip()
            opportunity_id = str(
                metadata.get("strategic_opportunity_id", "")
            ).strip()
            job_id = str(job.get("job_id", "")).strip()
            if not execution_id or not goal_id or not opportunity_id or not job_id:
                continue
            if self.store.get_record(execution_id) is not None:
                continue
            opportunity = self.project_intelligence.store.get_opportunity(
                opportunity_id
            ) or {}
            record = StrategicExecutionRecord(
                execution_id=execution_id,
                goal_id=goal_id,
                opportunity_id=opportunity_id,
                job_id=job_id,
                status=self._normalize_outcome(
                    job.get("state", "QUEUED"),
                    opportunity=opportunity,
                    job=job,
                ),
                target=str(opportunity.get("target", "")),
                objective=str(opportunity.get("objective", "")),
                metadata={"recovered_after_restart": True},
            )
            saved = self.store.save_record(record)
            recovered.append(saved)
            self._record_history(
                "STRATEGIC_EXECUTION_RECOVERED",
                success=True,
                record=saved,
                outcome=saved.get("status", ""),
            )
        return recovered

    def _refresh_roadmap_best_effort(self, goal_id: str) -> None:
        if not bool(
            self.store.policy().get("auto_refresh_roadmap", True)
        ):
            return
        try:
            self.strategic_development.refresh()
            self.strategic_development.store.update_runtime({
                "active_goal_id": str(goal_id),
                "phase": "EXECUTING" if goal_id else "READY",
            })
        except Exception as error:
            self.store.update_runtime({
                "last_error": f"{type(error).__name__}: {error}"
            })

    def _finish_cycle(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime()
        updates = {
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_error": "; ".join(
                str(item) for item in (errors or [])
            ),
        }
        for key in (
            "active_execution_id",
            "active_job_id",
            "active_goal_id",
            "last_opportunity_id",
        ):
            if key in extra:
                updates[key] = str(extra.get(key, ""))
        self.store.update_runtime(updates)
        execution = self._mapping(extra.get("execution"))
        self._record_history(
            status,
            success=success,
            record=execution,
            outcome=phase,
            error=updates["last_error"],
        )
        return self._response(
            status,
            success=success,
            errors=errors,
            **extra,
        )

    def _record_history(
        self,
        status: str,
        *,
        success: bool,
        record: dict[str, Any],
        outcome: Any = "",
        error: Any = "",
    ) -> None:
        self.store.record_history({
            "status": status,
            "success": success,
            "phase": self.store.runtime().get("phase", ""),
            "execution_id": record.get("execution_id", ""),
            "goal_id": record.get("goal_id", ""),
            "opportunity_id": record.get("opportunity_id", ""),
            "job_id": record.get("job_id", ""),
            "outcome": outcome,
            "error": error,
        })

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "strategic_execution",
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "summary": self.store.summary(),
            "roadmap_summary": self.strategic_development.store.summary(),
            "project_summary": self.project_intelligence.store.summary(),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }


    def _strategic_recommendation(self) -> dict[str, Any]:
        portfolio = getattr(self, "strategic_portfolio_service", None)
        enabled = getattr(portfolio, "is_enabled", None)
        recommend = getattr(portfolio, "recommend_opportunity", None)
        if callable(enabled) and callable(recommend):
            try:
                if bool(enabled()):
                    result = recommend()
                    if isinstance(result, dict):
                        return result
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")
        return self.strategic_development.recommend_opportunity()

    def _notify_strategic_portfolio(
        self,
        execution: dict[str, Any],
    ) -> None:
        portfolio = getattr(self, "strategic_portfolio_service", None)
        observe = getattr(portfolio, "observe_execution", None)
        if not callable(observe):
            return
        try:
            observe(dict(execution))
        except Exception:
            return

    def _job(self, job_id: str) -> dict[str, Any] | None:
        store = self._long_running_store()
        return store.get_job(job_id) if store is not None and job_id else None

    def _long_running_store(self) -> Any:
        service = getattr(
            self.project_intelligence,
            "long_running_service",
            None,
        )
        return getattr(service, "store", None)

    @staticmethod
    def _is_constraints_deferral(job: dict[str, Any] | None) -> bool:
        if not isinstance(job, dict):
            return False
        result = dict(job.get("last_result", {}) or {})
        return bool(
            str(result.get("status", "")).upper()
            == "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS"
            or str(result.get("diagnostic_category", "")).upper()
            == "CONSTRAINTS_PAUSE"
        )

    @staticmethod
    def _diagnostic_category(job: dict[str, Any] | None) -> str:
        if not isinstance(job, dict):
            return ""
        result = dict(job.get("last_result", {}) or {})
        return str(result.get("diagnostic_category", "")).upper()

    @staticmethod
    def _mapping(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}


    def _autonomy_governance_metadata(self) -> dict[str, Any]:
        service = getattr(
            self,
            "safe_policy_deployment_service",
            None,
        )
        method = getattr(service, "execution_context", None)
        if callable(method):
            try:
                value = method()
                return dict(value) if isinstance(value, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def bootstrap_strategic_execution(
    controller: Any,
) -> StrategicExecutionService:
    service = getattr(controller, "strategic_execution_service", None)
    if service is None:
        project_intelligence = bootstrap_project_intelligence(controller)
        self_directed = bootstrap_self_directed_development(controller)
        strategic_development = bootstrap_strategic_development(controller)
        service = StrategicExecutionService(
            controller.project_root,
            project_intelligence=project_intelligence,
            self_directed=self_directed,
            strategic_development=strategic_development,
        )
        controller.strategic_execution_service = service
        project_intelligence.strategic_execution_service = service
        self_directed.strategic_execution_service = service
        strategic_development.strategic_execution_service = service
    service.store.compact()
    service.reconcile()
    return service

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
import traceback
from typing import Any

from .project_intelligence_models import (
    ACTIVE_OPPORTUNITY_STATES,
    TERMINAL_OPPORTUNITY_STATES,
)
from .project_intelligence_service import (
    ProjectIntelligenceService,
    bootstrap_project_intelligence,
)
from .self_directed_development_store import (
    SelfDirectedDevelopmentStore,
)


class SelfDirectedDevelopmentService:
    """B56 bounded scan -> choose -> dispatch -> observe -> learn loop."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        project_intelligence: ProjectIntelligenceService | Any,
        store: SelfDirectedDevelopmentStore | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.project_intelligence = project_intelligence
        self.store = store or SelfDirectedDevelopmentStore(self.project_root)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def run_cycle(
        self,
        *,
        force_dispatch: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            started_at = self._now()
            runtime = self._roll_daily_budget(self.store.runtime())
            policy = self.store.policy()
            self.store.update_runtime({
                "running": self.is_running(),
                "phase": "RECONCILING",
                "last_cycle_at": started_at,
                "last_error": "",
            })
            try:
                reconciliation = self.project_intelligence.reconcile()
                outcomes = self._observe_terminal_outcomes()
                runtime = self.store.runtime()
                active = self._active_opportunities()
                waiting = next(
                    (
                        item
                        for item in active
                        if str(item.get("status", "")).upper()
                        == "WAITING_APPROVAL"
                    ),
                    None,
                )
                if waiting and bool(
                    policy.get("pause_on_waiting_approval", True)
                ):
                    return self._finish_cycle(
                        "SELF_DIRECTED_WAITING_APPROVAL",
                        phase="WAITING_APPROVAL",
                        success=True,
                        active=active,
                        outcomes=outcomes,
                        reconciliation=reconciliation,
                        waiting_approval_job_id=str(
                            waiting.get("job_id", "")
                        ),
                        reason=(
                            "Aktywne zadanie wymaga jawnej akceptacji. "
                            "B56 nie uruchomi kolejnego zadania."
                        ),
                    )
                if active:
                    first = active[0]
                    return self._finish_cycle(
                        "SELF_DIRECTED_WAITING_FOR_ACTIVE_JOB",
                        phase="WAITING_FOR_JOB",
                        success=True,
                        active=active,
                        outcomes=outcomes,
                        reconciliation=reconciliation,
                        active_job_id=str(first.get("job_id", "")),
                    )
                if int(runtime.get("consecutive_failures", 0)) >= int(
                    policy.get("max_consecutive_failures", 3)
                ):
                    self.store.update_runtime({"paused": True})
                    return self._finish_cycle(
                        "SELF_DIRECTED_CIRCUIT_OPEN",
                        phase="CIRCUIT_OPEN",
                        success=False,
                        outcomes=outcomes,
                        reconciliation=reconciliation,
                        errors=[
                            "Przekroczono limit kolejnych niepowodzeń. "
                            "Wymagane jest jawne wznowienie B56."
                        ],
                    )
                cooldown_until = self._parse_time(
                    runtime.get("cooldown_until", "")
                )
                if cooldown_until and self._utc_now() < cooldown_until:
                    return self._finish_cycle(
                        "SELF_DIRECTED_COOLDOWN",
                        phase="COOLDOWN",
                        success=True,
                        outcomes=outcomes,
                        reconciliation=reconciliation,
                        reason=f"Cooldown do {cooldown_until.isoformat()}.",
                    )
                if int(runtime.get("dispatches_today", 0)) >= int(
                    policy.get("max_dispatches_per_day", 10)
                ):
                    return self._finish_cycle(
                        "SELF_DIRECTED_DAILY_BUDGET_EXHAUSTED",
                        phase="DAILY_BUDGET_EXHAUSTED",
                        success=True,
                        outcomes=outcomes,
                        reconciliation=reconciliation,
                    )

                scan: dict[str, Any] = {}
                summary = self.project_intelligence.store.summary()
                if self._scan_due(runtime, policy, summary):
                    self.store.update_runtime({"phase": "SCANNING"})
                    scan = self.project_intelligence.scan_project()
                    self.store.update_runtime({"last_scan_at": self._now()})
                    if not bool(scan.get("success", False)):
                        return self._finish_cycle(
                            "SELF_DIRECTED_SCAN_FAILED",
                            phase="SCAN_FAILED",
                            success=False,
                            scan=scan,
                            outcomes=outcomes,
                            reconciliation=reconciliation,
                            errors=list(scan.get("errors", [])),
                        )

                runtime = self.store.runtime()
                should_dispatch = bool(force_dispatch) or bool(
                    runtime.get("enabled", False)
                    and not runtime.get("paused", False)
                    and policy.get("auto_dispatch", False)
                )
                if not should_dispatch:
                    return self._finish_cycle(
                        "SELF_DIRECTED_CYCLE_OBSERVE_ONLY",
                        phase="OBSERVE_ONLY",
                        success=True,
                        scan=scan,
                        outcomes=outcomes,
                        reconciliation=reconciliation,
                    )

                self.store.update_runtime({"phase": "DISPATCHING"})
                dispatched: list[dict[str, Any]] = []
                for _ in range(
                    int(policy.get("max_dispatch_per_cycle", 1))
                ):
                    if len(self._active_opportunities()) >= int(
                        policy.get("max_active_jobs", 1)
                    ):
                        break
                    result = self._dispatch_next_candidate()
                    dispatched.append(result)
                    job_id = str(result.get("job_id", "")).strip()
                    if not bool(result.get("success", False)) or not job_id:
                        break
                    self._record_dispatch(job_id)

                if not dispatched:
                    return self._finish_cycle(
                        "SELF_DIRECTED_NO_DISPATCH",
                        phase="IDLE",
                        success=True,
                        scan=scan,
                        outcomes=outcomes,
                        reconciliation=reconciliation,
                    )
                last = dispatched[-1]
                dispatched_job_id = str(last.get("job_id", "")).strip()
                status = (
                    "SELF_DIRECTED_JOB_DISPATCHED"
                    if bool(last.get("success", False)) and dispatched_job_id
                    else "SELF_DIRECTED_NO_SAFE_CANDIDATE"
                )
                return self._finish_cycle(
                    status,
                    phase=(
                        "WAITING_FOR_JOB"
                        if bool(last.get("success", False)) and dispatched_job_id
                        else "IDLE"
                    ),
                    success=True,
                    scan=scan,
                    outcomes=outcomes,
                    reconciliation=reconciliation,
                    dispatched=dispatched,
                    active_job_id=dispatched_job_id,
                )
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                return self._finish_cycle(
                    "SELF_DIRECTED_CYCLE_FAILED",
                    phase="FAILED",
                    success=False,
                    errors=[message],
                    traceback=traceback.format_exc()[-12000:],
                )

    def start_background(self) -> dict[str, Any]:
        if self.is_running():
            return self._response(
                "SELF_DIRECTED_SUPERVISOR_ALREADY_RUNNING",
                success=True,
            )
        with self._lock:
            if self.is_running():
                return self._response(
                    "SELF_DIRECTED_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                )
            if self.project_intelligence.is_running():
                self.project_intelligence.stop_background()
            self.project_intelligence.long_running_service.start_background()
            policy = self.store.update_policy({
                "auto_dispatch": True,
                "auto_approve": False,
            })
            self._sync_project_policy(policy)
            self.store.update_runtime({
                "enabled": True,
                "paused": False,
                "running": True,
                "phase": "STARTING",
                "last_error": "",
            })
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-self-directed-development",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "SELF_DIRECTED_SUPERVISOR_STARTED",
                success=True,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        self.store.compact()
        if bool(self.store.runtime().get("enabled", False)):
            return self.start_background()
        return self._response(
            "SELF_DIRECTED_SUPERVISOR_DISABLED",
            success=True,
        )

    def stop_background(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=5.0)
        self.store.update_policy({"auto_dispatch": False})
        self.store.update_runtime({
            "enabled": False,
            "paused": False,
            "running": False,
            "phase": "STOPPED",
            "active_job_id": "",
            "waiting_approval_job_id": "",
        })
        return self._response(
            "SELF_DIRECTED_SUPERVISOR_STOPPED",
            success=True,
        )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({
            "paused": True,
            "phase": "PAUSED",
        })
        return self._response(
            "SELF_DIRECTED_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({
            "paused": False,
            "consecutive_failures": 0,
            "cooldown_until": "",
            "phase": "RESUMED",
            "last_error": "",
        })
        return self._response(
            "SELF_DIRECTED_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
        )

    def status(self) -> dict[str, Any]:
        self.project_intelligence.reconcile()
        active = self._active_opportunities()
        return self._response(
            "SELF_DIRECTED_DEVELOPMENT_STATUS",
            success=True,
            active=active,
            best=self.project_intelligence.select_best().get("selected", {}),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "SELF_DIRECTED_DEVELOPMENT_HISTORY",
            success=True,
            history=self.store.history(limit=limit),
        )

    def update_policy(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        policy = self.store.update_policy({
            **dict(updates),
            "auto_approve": False,
        })
        self._sync_project_policy(policy)
        return self._response(
            "SELF_DIRECTED_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        try:
            if self._stop_event.wait(18.0):
                return

            while not self._stop_event.is_set():
                try:
                    runtime = self.store.runtime()
                    if not bool(runtime.get("paused", False)):
                        self.run_cycle()
                except Exception as error:
                    self.store.update_runtime({
                        "phase": "FAILED",
                        "last_error": f"{type(error).__name__}: {error}",
                    })
                interval = float(
                    self.store.policy().get("interval_seconds", 60.0)
                )
                self._stop_event.wait(max(30.0, interval))
        finally:
            self.store.update_runtime({"running": False})

    def _observe_terminal_outcomes(self) -> list[dict[str, Any]]:
        outcomes: list[dict[str, Any]] = []
        for item in self.project_intelligence.store.list_opportunities(
            limit=1000,
            statuses=set(TERMINAL_OPPORTUNITY_STATES),
        ):
            job_id = str(item.get("job_id", "")).strip()
            if not job_id or self.store.has_observed(job_id):
                continue
            status = str(item.get("status", "UNKNOWN")).upper()
            completed = status == "COMPLETED"
            deferred = self._is_constraints_deferral(item)
            failed = not completed and not deferred
            outcome_status = (
                "DEFERRED_CONSTRAINTS" if deferred else status
            )
            runtime = self.store.runtime()
            failures = int(runtime.get("consecutive_failures", 0))
            if completed:
                failures = 0
            elif failed:
                failures += 1
            update = {
                "consecutive_failures": failures,
                "completed_total": int(runtime.get("completed_total", 0))
                + int(completed),
                "failed_total": int(runtime.get("failed_total", 0))
                + int(failed),
                "deferred_total": int(runtime.get("deferred_total", 0))
                + int(deferred),
                "last_outcome": {
                    "job_id": job_id,
                    "opportunity_id": item.get("opportunity_id", ""),
                    "status": outcome_status,
                    "error": item.get("last_error", ""),
                    "observed_at": self._now(),
                },
            }
            if failed:
                cooldown = float(
                    self.store.policy().get(
                        "cooldown_after_failure_seconds",
                        600.0,
                    )
                )
                update["cooldown_until"] = (
                    self._utc_now() + timedelta(seconds=cooldown)
                ).isoformat()
            else:
                update["cooldown_until"] = ""
            self.store.update_runtime(update)
            self.store.mark_observed(job_id)
            bridge = self._strategic_execution_bridge()
            if bridge is not None:
                bridge.observe_outcome(item, outcome_status)
            outcome = dict(update["last_outcome"])
            outcomes.append(outcome)
            self.store.record_history({
                "status": "SELF_DIRECTED_OUTCOME_OBSERVED",
                "success": completed or deferred,
                "phase": "LEARNING",
                "job_id": job_id,
                "opportunity_id": item.get("opportunity_id", ""),
                "outcome": outcome_status,
                "error": item.get("last_error", ""),
            })
        return outcomes

    def _is_constraints_deferral(
        self,
        item: dict[str, Any],
    ) -> bool:
        if str(item.get("status", "")).upper() != "CANCELLED":
            return False
        job_id = str(item.get("job_id", "")).strip()
        if not job_id:
            return False
        store = getattr(
            self.project_intelligence.long_running_service,
            "store",
            None,
        )
        job = store.get_job(job_id) if store is not None else None
        if not isinstance(job, dict):
            return False
        result = dict(job.get("last_result", {}) or {})
        return (
            str(result.get("status", "")).upper()
            == "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS"
            or str(result.get("diagnostic_category", "")).upper()
            == "CONSTRAINTS_PAUSE"
        )

    def _record_dispatch(self, job_id: str) -> None:
        runtime = self._roll_daily_budget(self.store.runtime())
        self.store.update_runtime({
            "last_dispatch_at": self._now(),
            "last_dispatch_job_id": job_id,
            "active_job_id": job_id,
            "dispatches_today": int(runtime.get("dispatches_today", 0)) + 1,
        })
        self.store.record_history({
            "status": "SELF_DIRECTED_JOB_DISPATCHED",
            "success": True,
            "phase": "DISPATCHING",
            "job_id": job_id,
        })

    def _finish_cycle(
        self,
        status: str,
        *,
        phase: str,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime()
        result_summary = {
            "status": status,
            "success": success,
            "phase": phase,
            "job_id": str(
                extra.get("active_job_id", "")
                or extra.get("waiting_approval_job_id", "")
            ),
        }
        updates = {
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_result": result_summary,
            "last_error": "; ".join(str(item) for item in (errors or [])),
            "active_job_id": str(extra.get("active_job_id", "")),
            "waiting_approval_job_id": str(
                extra.get("waiting_approval_job_id", "")
            ),
        }
        self.store.update_runtime(updates)
        self.store.record_history({
            **result_summary,
            "error": updates["last_error"],
            "reason": extra.get("reason", ""),
            "scan_status": (
                extra.get("scan", {}).get("status", "")
                if isinstance(extra.get("scan"), dict)
                else ""
            ),
            "dispatch_status": (
                extra.get("dispatched", [{}])[-1].get("status", "")
                if isinstance(extra.get("dispatched"), list)
                and extra.get("dispatched")
                and isinstance(extra.get("dispatched")[-1], dict)
                else ""
            ),
        })
        return self._response(
            status,
            success=success,
            errors=errors,
            **extra,
        )

    def _dispatch_next_candidate(self) -> dict[str, Any]:
        strategic = getattr(
            self,
            "strategic_development_service",
            None,
        )
        if strategic is not None and bool(strategic.is_enabled()):
            bridge = self._strategic_execution_bridge()
            if bridge is not None:
                return bridge.dispatch_next()
            recommendation = strategic.recommend_opportunity()
            selected = recommendation.get("recommendation", {})
            opportunity_id = str(
                selected.get("opportunity_id", "")
                if isinstance(selected, dict)
                else ""
            ).strip()
            if opportunity_id:
                result = self.project_intelligence.dispatch_opportunity(
                    opportunity_id,
                    force=True,
                )
                if isinstance(result, dict):
                    result = {
                        **result,
                        "strategic_goal": recommendation.get("selected", {}),
                        "strategic_status": recommendation.get("status", ""),
                    }
                return result
        return self.project_intelligence.dispatch_best(force=True)

    def _strategic_execution_bridge(self) -> Any:
        service = getattr(self, "strategic_execution_service", None)
        if service is not None:
            return service
        strategic = getattr(
            self,
            "strategic_development_service",
            None,
        )
        if strategic is None:
            return None
        from .strategic_execution_service import StrategicExecutionService

        service = StrategicExecutionService(
            self.project_root,
            project_intelligence=self.project_intelligence,
            self_directed=self,
            strategic_development=strategic,
        )
        self.strategic_execution_service = service
        strategic.strategic_execution_service = service
        self.project_intelligence.strategic_execution_service = service
        return service

    def _active_opportunities(self) -> list[dict[str, Any]]:
        return self.project_intelligence.store.list_opportunities(
            limit=1000,
            statuses=set(ACTIVE_OPPORTUNITY_STATES),
        )

    def _scan_due(
        self,
        runtime: dict[str, Any],
        policy: dict[str, Any],
        summary: dict[str, Any],
    ) -> bool:
        if int(summary.get("pending", 0)) < int(
            policy.get("rescan_backlog_below", 20)
        ):
            return True
        last_scan = self._parse_time(runtime.get("last_scan_at", ""))
        if last_scan is None:
            return True
        interval = float(policy.get("scan_interval_seconds", 300.0))
        return (self._utc_now() - last_scan).total_seconds() >= interval

    def _roll_daily_budget(
        self,
        runtime: dict[str, Any],
    ) -> dict[str, Any]:
        today = self._utc_now().date().isoformat()
        if str(runtime.get("dispatch_day", "")) == today:
            return runtime
        return self.store.update_runtime({
            "dispatch_day": today,
            "dispatches_today": 0,
        })

    def _sync_project_policy(
        self,
        policy: dict[str, Any],
    ) -> None:
        self.project_intelligence.update_policy({
            "max_active_jobs": int(policy.get("max_active_jobs", 1)),
            "max_dispatch_per_cycle": int(
                policy.get("max_dispatch_per_cycle", 1)
            ),
            "auto_dispatch": False,
            "auto_approve": False,
            "auto_rollback": bool(policy.get("auto_rollback", True)),
            "final_validation": bool(policy.get("final_validation", True)),
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
            "operation": "self_directed_development",
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "project_summary": self.project_intelligence.store.summary(),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def bootstrap_self_directed_development(
    controller: Any,
) -> SelfDirectedDevelopmentService:
    service = getattr(
        controller,
        "self_directed_development_service",
        None,
    )
    if service is None:
        project_intelligence = bootstrap_project_intelligence(controller)
        service = SelfDirectedDevelopmentService(
            controller.project_root,
            project_intelligence=project_intelligence,
        )
        controller.self_directed_development_service = service
    service.start_if_enabled()
    return service

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import traceback
from typing import Any, Callable
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore


class _CycleStopRequested(RuntimeError):
    pass


class FullAutonomy24x7Service:
    """B68 bounded, persistent orchestration across B55-B67."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        resource_budget: Any,
        project_intelligence: Any,
        self_directed: Any,
        strategic_development: Any,
        strategic_execution: Any,
        strategic_portfolio: Any,
        strategic_policy_evolution: Any,
        strategic_policy_validation: Any,
        safe_policy_deployment: Any,
        goal_governance: Any,
        causal_learning: Any,
        release_manager: Any,
        self_maintenance: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.resource_budget = resource_budget
        self.project_intelligence = project_intelligence
        self.self_directed = self_directed
        self.strategic_development = strategic_development
        self.strategic_execution = strategic_execution
        self.strategic_portfolio = strategic_portfolio
        self.strategic_policy_evolution = strategic_policy_evolution
        self.strategic_policy_validation = strategic_policy_validation
        self.safe_policy_deployment = safe_policy_deployment
        self.goal_governance = goal_governance
        self.causal_learning = causal_learning
        self.release_manager = release_manager
        self.self_maintenance = self_maintenance
        self._lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._worker_finalizer: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._active_cycle_token = ""
        self._active_lease_id = ""
        self._active_done_event: threading.Event | None = None
        self._timed_out_tokens: set[str] = set()
        self._recover_owner_leases("B68_SERVICE_INITIALIZATION_RECOVERY")
        self._reconcile_stopped_worker_state(
            "B68_SERVICE_INITIALIZATION_RECONCILIATION"
        )

    def run_cycle(self) -> dict[str, Any]:
        with self._lock:
            policy = self.store.policy("B68")
            runtime = self._roll_day(self.store.runtime("B68"))
            if not bool(policy.get("enabled", False)):
                return self._response(
                    "FULL_24X7_AUTONOMY_DISABLED",
                    success=True,
                    decision="HOLD",
                )
            if bool(runtime.get("paused", False)):
                return self._response(
                    "FULL_24X7_AUTONOMY_PAUSED",
                    success=True,
                    decision="HOLD",
                )
            if int(runtime.get("cycles_used_today", 0)) >= int(
                policy.get("max_daily_cycles", 24)
            ):
                return self._finish(
                    "FULL_24X7_AUTONOMY_DAILY_LIMIT",
                    success=True,
                    phase="COOLDOWN",
                    decision="DEFER",
                    steps={},
                )

            lease = self.resource_budget.acquire("B68")
            if not bool(lease.get("allowed", False)):
                return self._finish(
                    "FULL_24X7_AUTONOMY_DEFERRED_RESOURCES",
                    success=True,
                    phase="WAITING_RESOURCES",
                    decision="DEFER",
                    steps={"B64": lease},
                )

            lease_id = str(lease.get("lease", {}).get("lease_id", ""))
            cycle_token = f"b68-cycle-{uuid4().hex}"
            done_event = threading.Event()
            self._activate_cycle(cycle_token, lease_id, done_event)
            self._start_watchdog(
                cycle_token,
                lease_id,
                done_event,
                float(policy.get("max_cycle_seconds", 600.0)),
            )

            steps: dict[str, Any] = {"B64": lease}
            success = True
            error = ""
            stopped = False
            timed_out = False
            try:
                steps["B55"] = self._run_step(
                    "B55",
                    lambda: self.project_intelligence.run_cycle(dispatch=False),
                )
                steps["B63"] = self._run_step(
                    "B63",
                    self.goal_governance.run_cycle,
                )
                steps["B57"] = self._run_managed_step(
                    "B57",
                    self.strategic_development,
                    self.strategic_development.run_cycle,
                )
                steps["B59"] = self._run_step(
                    "B59",
                    self.strategic_portfolio.rebalance,
                )
                steps["B58_RECONCILE"] = self._run_step(
                    "B58_RECONCILE",
                    self.strategic_execution.reconcile,
                )
                execution_summary = self.strategic_execution.store.summary()
                waiting = int(execution_summary.get("waiting_approval", 0))
                active = int(execution_summary.get("active", 0))
                if (
                    bool(policy.get("auto_dispatch", True))
                    and active == 0
                    and waiting == 0
                ):
                    steps["B58_DISPATCH"] = self._run_step(
                        "B58_DISPATCH",
                        self.strategic_execution.dispatch_next,
                    )
                else:
                    steps["B58_DISPATCH"] = {
                        "success": True,
                        "status": "FULL_24X7_DISPATCH_HELD",
                        "reason": "Aktywne zadanie lub WAITING_APPROVAL.",
                    }
                steps["B60"] = self._run_step(
                    "B60",
                    lambda: self.strategic_policy_evolution.learn(
                        apply_if_safe=False
                    ),
                )
                steps["B61"] = self._run_step(
                    "B61",
                    self.strategic_policy_validation.run_cycle,
                )
                steps["B62"] = self._run_step(
                    "B62",
                    self.safe_policy_deployment.run_cycle,
                )
                steps["B65"] = self._run_step(
                    "B65",
                    self.causal_learning.run_cycle,
                )
                if bool(policy.get("run_maintenance_scan", True)):
                    steps["B67"] = self._run_step(
                        "B67",
                        self.self_maintenance.scan,
                    )
                if bool(policy.get("run_release_planning", True)):
                    steps["B66"] = self._run_step(
                        "B66",
                        self.release_manager.run_cycle,
                    )
                success = all(
                    bool(value.get("success", False))
                    for value in steps.values()
                    if isinstance(value, dict)
                )
            except _CycleStopRequested:
                stopped = True
                steps["stop"] = {
                    "success": True,
                    "status": "FULL_24X7_STOP_REQUEST_OBSERVED",
                }
            except Exception as exception:
                success = False
                error = f"{type(exception).__name__}: {exception}"
                steps["exception"] = {
                    "success": False,
                    "status": "FULL_24X7_STEP_EXCEPTION",
                    "error": error,
                    "traceback": traceback.format_exc()[-12000:],
                }
            finally:
                done_event.set()
                timed_out = self._cycle_timed_out(cycle_token)
                release_result = self.resource_budget.release(
                    lease_id,
                    success=success and not timed_out,
                    reason=(
                        "B68_CYCLE_TIMEOUT"
                        if timed_out else error
                    ),
                )
                steps["B64_RELEASE"] = release_result
                self._clear_active_cycle(cycle_token)

            if timed_out:
                success = False
                error = "Przekroczono maksymalny czas cyklu B68."
                status = "FULL_24X7_AUTONOMY_CYCLE_TIMED_OUT"
                phase = "CYCLE_TIMEOUT"
                decision = "STOP"
            elif stopped or self._stop_event.is_set():
                status = "FULL_24X7_AUTONOMY_CYCLE_STOPPED"
                phase = "STOPPED"
                decision = "STOP"
            else:
                status = (
                    "FULL_24X7_AUTONOMY_CYCLE_COMPLETED"
                    if success else "FULL_24X7_AUTONOMY_CYCLE_FAILED"
                )
                phase = "RUNNING" if self.is_running() else "READY"
                decision = "CONTINUE" if success else "FAILURE"
            return self._finish(
                status,
                success=success,
                phase=phase,
                decision=decision,
                steps=steps,
                error=error,
            )

    def start_background(self) -> dict[str, Any]:
        with self._lock:
            self._reconcile_stopped_worker_state(
                "B68_START_RECONCILIATION"
            )
            if self.is_running():
                return self._response(
                    "FULL_24X7_AUTONOMY_ALREADY_RUNNING",
                    success=True,
                )
            recovery = self._recover_owner_leases("B68_START_RECOVERY")
            self.store.update_policy("B68", {
                "enabled": True,
                "auto_approve": False,
            })
            self.store.update_runtime("B68", {
                "enabled": True,
                "paused": False,
                "running": True,
                "phase": "STARTING",
                "last_status": "FULL_24X7_AUTONOMY_STARTING",
                "last_error": "",
            })
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-full-autonomy-24x7",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "FULL_24X7_AUTONOMY_STARTED",
                success=True,
                recovery=recovery,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        policy = self.store.policy("B68")
        runtime = self.store.runtime("B68")
        if bool(policy.get("enabled", False)) and bool(runtime.get("enabled", False)):
            return self.start_background()
        return self._response(
            "FULL_24X7_AUTONOMY_DISABLED",
            success=True,
        )

    def stop_background(self) -> dict[str, Any]:
        self._stop_event.set()
        self._cancel_watchdog()
        policy = self.store.policy("B68")
        thread = self._thread
        join_seconds = float(policy.get("stop_join_seconds", 10.0))
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=max(1.0, join_seconds))
        worker_alive = bool(thread and thread.is_alive())
        recovery = self._recover_owner_leases("B68_STOP_RECOVERY")
        runtime = self.store.update_runtime("B68", {
            "enabled": False,
            "paused": False,
            "running": False,
            "phase": "STOPPED_PENDING_WORKER" if worker_alive else "STOPPED",
            "last_status": (
                "FULL_24X7_AUTONOMY_STOPPED_PENDING_WORKER"
                if worker_alive else "FULL_24X7_AUTONOMY_STOPPED"
            ),
            "last_decision": "STOP",
            "last_error": (
                "Cykl nadal kończy krok w tle; dzierżawa B64 została odzyskana."
                if worker_alive else ""
            ),
        })
        self.store.update_policy("B68", {"enabled": False, "auto_approve": False})
        if worker_alive and thread is not None:
            self._start_worker_finalizer(thread)
        elif not worker_alive:
            with self._state_lock:
                if self._thread is thread:
                    self._thread = None
        return self._response(
            "FULL_24X7_AUTONOMY_STOPPED_PENDING_WORKER"
            if worker_alive else "FULL_24X7_AUTONOMY_STOPPED",
            success=True,
            runtime=runtime,
            recovery=recovery,
            worker_alive=worker_alive,
        )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime("B68", {
            "paused": True,
            "phase": "PAUSED",
        })
        return self._response(
            "FULL_24X7_AUTONOMY_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume(self) -> dict[str, Any]:
        runtime = self.store.update_runtime("B68", {
            "enabled": True,
            "paused": False,
            "phase": "RESUMING",
        })
        self.store.update_policy("B68", {"enabled": True, "auto_approve": False})
        if not self.is_running():
            return self.start_background()
        return self._response(
            "FULL_24X7_AUTONOMY_RESUMED",
            success=True,
            runtime=runtime,
        )

    def status(self) -> dict[str, Any]:
        runtime = self._reconcile_stopped_worker_state(
            "B68_STATUS_RECONCILIATION"
        )
        return self._response(
            "FULL_24X7_AUTONOMY_STATUS",
            success=True,
            runtime=runtime,
            cycles=self.store.list_records("B68", limit=10),
            resource_status=self.resource_budget.status(),
            execution_summary=self.strategic_execution.store.summary(),
            stage_summaries={
                stage: self.store.summary(stage)
                for stage in ("B62", "B63", "B64", "B65", "B66", "B67", "B68")
            },
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "FULL_24X7_AUTONOMY_HISTORY",
            success=True,
            cycles=self.store.list_records("B68", limit=limit),
            history=self.store.history(stage="B68", limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B68", {
            **dict(updates),
            "auto_approve": False,
        })
        return self._response(
            "FULL_24X7_AUTONOMY_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        session_cycles = 0
        try:
            self.store.update_runtime("B68", {
                "running": True,
                "phase": "RUNNING",
            })
            while not self._stop_event.is_set():
                policy = self.store.policy("B68")
                if session_cycles >= int(policy.get("max_cycles_per_session", 100)):
                    self.store.update_runtime("B68", {
                        "phase": "MAX_CYCLES_REACHED",
                    })
                    break
                if not bool(self.store.runtime("B68").get("paused", False)):
                    self.run_cycle()
                    session_cycles += 1
                    failures = int(
                        self.store.runtime("B68").get("consecutive_failures", 0)
                    )
                    if failures >= int(
                        policy.get("stop_after_consecutive_failures", 3)
                    ):
                        self.store.update_runtime("B68", {
                            "phase": "CIRCUIT_BREAKER",
                            "last_error": "Przekroczono limit kolejnych błędów B68.",
                        })
                        break
                interval = float(policy.get("interval_seconds", 300.0))
                jitter = float(policy.get("interval_jitter_seconds", 17.0))
                self._stop_event.wait(max(60.0, interval + jitter))
        finally:
            runtime = self.store.runtime("B68")
            phase = str(runtime.get("phase", "READY"))
            terminal = {
                "CYCLE_TIMEOUT",
                "CIRCUIT_BREAKER",
                "MAX_CYCLES_REACHED",
            }
            if self._stop_event.is_set() and phase not in terminal:
                phase = "STOPPED"
            elif not self._stop_event.is_set() and phase == "RUNNING":
                phase = "READY"
            updates: dict[str, Any] = {
                "running": False,
                "phase": phase,
            }
            if phase == "STOPPED":
                updates.update({
                    "enabled": False,
                    "last_status": "FULL_24X7_AUTONOMY_STOPPED",
                    "last_decision": "STOP",
                    "last_error": "",
                })
            self.store.update_runtime("B68", updates)

    def _run_managed_step(
        self,
        stage: str,
        service: Any,
        callback: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        is_running = getattr(service, "is_running", None)
        if callable(is_running):
            try:
                supervisor_running = bool(is_running())
            except Exception:
                supervisor_running = False
            if supervisor_running:
                label = str(stage).upper().replace(" ", "_")[:50]
                self.store.update_runtime("B68", {
                    "phase": f"OBSERVING_{label}_SUPERVISOR",
                    "last_status": f"FULL_24X7_STEP_{label}_DELEGATED",
                    "last_decision": "OBSERVE",
                })
                return {
                    "success": True,
                    "status": f"FULL_24X7_STEP_{label}_DELEGATED",
                    "decision": "OBSERVE",
                    "reason": (
                        f"Nadzorca {label} jest już aktywny; "
                        "B68 nie uruchamia konkurencyjnego cyklu."
                    ),
                }
        return self._run_step(stage, callback)

    def _run_step(
        self,
        stage: str,
        callback: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if self._stop_event.is_set():
            raise _CycleStopRequested()
        label = str(stage).upper().replace(" ", "_")[:50]
        self.store.update_runtime("B68", {
            "phase": f"RUNNING_{label}",
            "last_status": f"FULL_24X7_STEP_{label}",
            "last_decision": "RUN",
        })
        result = callback()
        if not isinstance(result, dict):
            return {
                "success": False,
                "status": f"FULL_24X7_STEP_{label}_INVALID_RESULT",
            }
        return result

    def _start_watchdog(
        self,
        token: str,
        lease_id: str,
        done_event: threading.Event,
        timeout_seconds: float,
    ) -> None:
        thread = threading.Thread(
            target=self._watch_cycle,
            args=(token, lease_id, done_event, max(120.0, timeout_seconds)),
            name="jarvis-b68-cycle-watchdog",
            daemon=True,
        )
        thread.start()

    def _watch_cycle(
        self,
        token: str,
        lease_id: str,
        done_event: threading.Event,
        timeout_seconds: float,
    ) -> None:
        if done_event.wait(timeout_seconds):
            return
        with self._state_lock:
            if token != self._active_cycle_token:
                return
            self._timed_out_tokens.add(token)
        self._stop_event.set()
        recovery = self._recover_owner_leases("B68_CYCLE_TIMEOUT_RECOVERY")
        self.store.update_policy("B68", {"enabled": False, "auto_approve": False})
        self.store.update_runtime("B68", {
            "enabled": False,
            "running": False,
            "phase": "CYCLE_TIMEOUT",
            "last_status": "FULL_24X7_AUTONOMY_CYCLE_TIMED_OUT",
            "last_decision": "STOP",
            "last_error": (
                "Cykl B68 przekroczył limit czasu; dzierżawa B64 została odzyskana."
            ),
        })
        self.store.record_history("B68", {
            "status": "FULL_24X7_AUTONOMY_CYCLE_TIMED_OUT",
            "success": False,
            "phase": "CYCLE_TIMEOUT",
            "decision": "STOP",
            "reason": str(recovery.get("status", "")),
            "error": f"Timeout cyklu; lease={lease_id}",
        })

    def _activate_cycle(
        self,
        token: str,
        lease_id: str,
        done_event: threading.Event,
    ) -> None:
        with self._state_lock:
            self._active_cycle_token = token
            self._active_lease_id = lease_id
            self._active_done_event = done_event

    def _clear_active_cycle(self, token: str) -> None:
        with self._state_lock:
            if token == self._active_cycle_token:
                self._active_cycle_token = ""
                self._active_lease_id = ""
                self._active_done_event = None
            self._timed_out_tokens.discard(token)

    def _cycle_timed_out(self, token: str) -> bool:
        with self._state_lock:
            return token in self._timed_out_tokens

    def _cancel_watchdog(self) -> None:
        with self._state_lock:
            event = self._active_done_event
        if event is not None:
            event.set()

    def _start_worker_finalizer(
        self,
        worker: threading.Thread,
    ) -> None:
        with self._state_lock:
            current = self._worker_finalizer
            if current is not None and current.is_alive():
                return
            finalizer = threading.Thread(
                target=self._wait_for_worker_exit,
                args=(worker,),
                name="jarvis-b68-worker-finalizer",
                daemon=True,
            )
            self._worker_finalizer = finalizer
        finalizer.start()

    def _wait_for_worker_exit(
        self,
        worker: threading.Thread,
    ) -> None:
        worker.join()
        if worker.is_alive():
            return
        with self._state_lock:
            if self._thread is worker:
                self._thread = None
        runtime = self._reconcile_stopped_worker_state(
            "B68_WORKER_EXIT_RECONCILIATION"
        )
        if str(runtime.get("phase", "")) == "STOPPED":
            self.store.record_history("B68", {
                "status": "FULL_24X7_AUTONOMY_WORKER_FINALIZED",
                "success": True,
                "phase": "STOPPED",
                "decision": "STOP",
                "reason": "Worker zakończył ostatni krok po żądaniu STOP.",
                "error": "",
            })

    def _reconcile_stopped_worker_state(
        self,
        reason: str,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B68")
        if str(runtime.get("phase", "")) != "STOPPED_PENDING_WORKER":
            return runtime
        if self.is_running():
            return runtime
        runtime = self.store.update_runtime("B68", {
            "enabled": False,
            "paused": False,
            "running": False,
            "phase": "STOPPED",
            "last_status": "FULL_24X7_AUTONOMY_STOPPED",
            "last_decision": "STOP",
            "last_error": "",
        })
        self.store.update_policy("B68", {
            "enabled": False,
            "auto_approve": False,
        })
        self.store.record_history("B68", {
            "status": "FULL_24X7_AUTONOMY_PENDING_WORKER_RECONCILED",
            "success": True,
            "phase": "STOPPED",
            "decision": "STOP",
            "reason": reason,
            "error": "",
        })
        return runtime

    def _recover_owner_leases(self, reason: str) -> dict[str, Any]:
        method = getattr(self.resource_budget, "release_owner_leases", None)
        if not callable(method):
            return {
                "success": True,
                "status": "RESOURCE_BUDGET_OWNER_RECOVERY_UNAVAILABLE",
                "released_count": 0,
            }
        try:
            result = method("B68", success=True, reason=reason)
            return dict(result) if isinstance(result, dict) else {
                "success": True,
                "status": "RESOURCE_BUDGET_OWNER_RECOVERY_COMPLETED",
            }
        except Exception as exception:
            return {
                "success": False,
                "status": "RESOURCE_BUDGET_OWNER_RECOVERY_FAILED",
                "errors": [f"{type(exception).__name__}: {exception}"],
            }

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        steps: dict[str, Any],
        error: str = "",
    ) -> dict[str, Any]:
        runtime = self._roll_day(self.store.runtime("B68"))
        failures = 0 if success else int(runtime.get("consecutive_failures", 0)) + 1
        if self._stop_event.is_set() and phase not in {"CYCLE_TIMEOUT", "STOPPED"}:
            phase = "STOPPED"
            decision = "STOP"
        cycle = self.store.append_record("B68", {
            "cycle_id": f"autonomy-cycle-{uuid4().hex}",
            "status": "COMPLETED" if success else "FAILED",
            "decision": decision,
            "steps": self._compact_steps(steps),
            "error": error,
            "created_at": self._now(),
        })
        runtime = self.store.update_runtime("B68", {
            "enabled": bool(self.store.policy("B68").get("enabled", False)),
            "running": self.is_running() and not self._stop_event.is_set(),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "cycles_used_today": int(runtime.get("cycles_used_today", 0)) + 1,
            "consecutive_failures": failures,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": decision,
            "last_record_id": str(cycle.get("cycle_id", "")),
            "last_result": {"status": status, "success": success},
            "last_error": error,
        })
        response = self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            cycle=cycle,
            steps=steps,
        )
        self.store.record_history("B68", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "error": error,
        })
        return response

    def _roll_day(self, runtime: dict[str, Any]) -> dict[str, Any]:
        today = datetime.now(timezone.utc).date().isoformat()
        if str(runtime.get("budget_date", "")) == today:
            return runtime
        return self.store.update_runtime("B68", {
            "budget_date": today,
            "cycles_used_today": 0,
            "consecutive_failures": 0,
        })

    @staticmethod
    def _compact_steps(steps: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in steps.items():
            if not isinstance(value, dict):
                continue
            result[str(key)] = {
                "success": bool(value.get("success", False)),
                "status": str(value.get("status", "UNKNOWN"))[:150],
                "decision": str(value.get("decision", ""))[:100],
                "reason": str(value.get("reason", ""))[-1000:],
            }
        return result

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
            "operation": "autonomy_governance_suite",
            "stage": "B68",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B68"))),
            "policy": dict(extra.pop("policy", self.store.policy("B68"))),
            "summary": self.store.summary("B68"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

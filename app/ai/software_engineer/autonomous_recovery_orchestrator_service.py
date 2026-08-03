from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore


_ACTIVE_INCIDENT_STATUSES = {"OPEN", "CONTAINED"}
_ACTIVE_PLAN_STATUSES = {
    "PREVIEW_READY",
    "RUNNING",
    "VERIFICATION_REQUIRED",
    "VERIFICATION_FAILED",
}

_SAFE_RUNBOOKS: dict[str, tuple[str, ...]] = {
    "RESOURCE_LEASE_OVERFLOW": (
        "STOP_B68",
        "RELEASE_B68_LEASES",
        "NORMALIZE_B64_RUNTIME",
        "RESCAN_B69",
        "VERIFY_RECOVERY",
    ),
    "ORPHANED_B68_LEASE": (
        "STOP_B68",
        "RELEASE_B68_LEASES",
        "NORMALIZE_B64_RUNTIME",
        "RESCAN_B69",
        "VERIFY_RECOVERY",
    ),
    "RESOURCE_RUNTIME_MISMATCH": (
        "NORMALIZE_B64_RUNTIME",
        "RESCAN_B69",
        "VERIFY_RECOVERY",
    ),
    "B68_CYCLE_TIMEOUT": (
        "STOP_B68",
        "RELEASE_B68_LEASES",
        "FINALIZE_B68_STOP",
        "RESCAN_B69",
        "VERIFY_RECOVERY",
    ),
    "B68_CIRCUIT_BREAKER": (
        "STOP_B68",
        "RELEASE_B68_LEASES",
        "FINALIZE_B68_STOP",
        "RESCAN_B69",
        "VERIFY_RECOVERY",
    ),
    "B68_PENDING_WORKER_STALE": (
        "STOP_B68",
        "RELEASE_B68_LEASES",
        "FINALIZE_B68_STOP",
        "RESCAN_B69",
        "VERIFY_RECOVERY",
    ),
    "B68_HEARTBEAT_STALE": (
        "STOP_B68",
        "RELEASE_B68_LEASES",
        "FINALIZE_B68_STOP",
        "RESCAN_B69",
        "VERIFY_RECOVERY",
    ),
}


class AutonomousRecoveryOrchestratorService:
    """B70 bounded recovery planning, execution and verification."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        incident_response: Any,
        resource_budget: Any,
        full_autonomy: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.incident_response = incident_response
        self.resource_budget = resource_budget
        self.full_autonomy = full_autonomy
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._reconcile_runtime_after_restart()

    def run_cycle(self) -> dict[str, Any]:
        with self._lock:
            scan = self.incident_response.scan()
            incident = self._latest_actionable_incident()
            if incident is None:
                return self._finish(
                    "AUTONOMOUS_RECOVERY_CYCLE_CLEAR",
                    success=True,
                    phase="READY",
                    decision="CLEAR",
                    scan=scan,
                    plan=None,
                )
            plan = self._active_plan_for_incident(
                str(incident.get("incident_id", ""))
            )
            if plan is None:
                plan = self._create_plan(incident)
            return self._finish(
                "AUTONOMOUS_RECOVERY_CYCLE_PLANNED",
                success=True,
                phase="PREVIEW_READY" if plan.get("status") != "BLOCKED" else "BLOCKED",
                decision="PREVIEW" if plan.get("status") != "BLOCKED" else "HOLD",
                scan=scan,
                plan=plan,
            )

    def plan_latest(self) -> dict[str, Any]:
        with self._lock:
            incident = self._latest_actionable_incident()
            if incident is None:
                return self._response(
                    "AUTONOMOUS_RECOVERY_NO_INCIDENT",
                    success=True,
                    decision="HOLD",
                    reason="Brak otwartego incydentu wymagającego odzyskiwania.",
                )
            incident_id = str(incident.get("incident_id", ""))
            existing = self._active_plan_for_incident(incident_id)
            plan = existing or self._create_plan(incident)
            decision = "PREVIEW" if plan.get("status") != "BLOCKED" else "HOLD"
            return self._response(
                "AUTONOMOUS_RECOVERY_PLAN_READY"
                if decision == "PREVIEW"
                else "AUTONOMOUS_RECOVERY_PLAN_BLOCKED",
                success=True,
                decision=decision,
                plan=plan,
                incident=incident,
            )

    def execute_latest(self) -> dict[str, Any]:
        with self._lock:
            plan = self._latest_executable_plan()
            if plan is None:
                prepared = self.plan_latest()
                plan = dict(prepared.get("plan", {}) or {})
            if not plan:
                return self._response(
                    "AUTONOMOUS_RECOVERY_NOTHING_TO_EXECUTE",
                    success=True,
                    decision="HOLD",
                )
            if str(plan.get("status", "")).upper() == "BLOCKED":
                return self._response(
                    "AUTONOMOUS_RECOVERY_EXECUTION_BLOCKED",
                    success=True,
                    decision="HOLD",
                    reason=str(plan.get("blocked_reason", "Brak bezpiecznego runbooka.")),
                    plan=plan,
                )

            policy = self.store.policy("B70")
            attempts = int(plan.get("attempts", 0) or 0)
            maximum = int(policy.get("max_attempts_per_incident", 3) or 3)
            if attempts >= maximum:
                plan = self._update_plan(plan, {
                    "status": "EXHAUSTED",
                    "last_error": "Przekroczono limit prób odzyskiwania.",
                    "updated_at": self._now(),
                })
                return self._response(
                    "AUTONOMOUS_RECOVERY_ATTEMPTS_EXHAUSTED",
                    success=False,
                    decision="ESCALATE",
                    errors=[str(plan.get("last_error", ""))],
                    plan=plan,
                )

            plan = self._update_plan(plan, {
                "status": "RUNNING",
                "attempts": attempts + 1,
                "started_at": self._now(),
                "updated_at": self._now(),
            })
            actions: list[dict[str, Any]] = []
            for step in list(plan.get("steps", [])):
                result = self._execute_step(str(step), plan)
                actions.append(result)
                if not bool(result.get("success", False)):
                    break

            action_success = all(bool(item.get("success", False)) for item in actions)
            verification = self._verify_plan(plan, rescan=False)
            verified = bool(verification.get("verified", False))
            status = "COMPLETED" if action_success and verified else "VERIFICATION_FAILED"
            decision = "RECOVERED" if status == "COMPLETED" else "ESCALATE"
            plan = self._update_plan(plan, {
                "status": status,
                "actions": actions,
                "verification": verification,
                "completed_at": self._now() if status == "COMPLETED" else "",
                "last_error": "" if status == "COMPLETED" else str(
                    verification.get("reason", "Odzyskanie nie zostało potwierdzone.")
                ),
                "updated_at": self._now(),
                "auto_approve": False,
            })
            self.store.update_runtime("B70", {
                "phase": status,
                "last_status": "AUTONOMOUS_RECOVERY_COMPLETED"
                if status == "COMPLETED"
                else "AUTONOMOUS_RECOVERY_VERIFICATION_FAILED",
                "last_decision": decision,
                "last_record_id": str(plan.get("recovery_id", "")),
                "last_result": {
                    "status": status,
                    "success": status == "COMPLETED",
                    "incident_id": str(plan.get("incident_id", "")),
                },
                "last_error": str(plan.get("last_error", "")),
            })
            self.store.record_history("B70", {
                "status": "AUTONOMOUS_RECOVERY_COMPLETED"
                if status == "COMPLETED"
                else "AUTONOMOUS_RECOVERY_VERIFICATION_FAILED",
                "success": status == "COMPLETED",
                "phase": status,
                "decision": decision,
                "reason": str(plan.get("category", "")),
                "error": str(plan.get("last_error", "")),
                "metadata": {
                    "recovery_id": str(plan.get("recovery_id", "")),
                    "incident_id": str(plan.get("incident_id", "")),
                    "actions": actions,
                },
            })
            return self._response(
                "AUTONOMOUS_RECOVERY_COMPLETED"
                if status == "COMPLETED"
                else "AUTONOMOUS_RECOVERY_VERIFICATION_FAILED",
                success=status == "COMPLETED",
                decision=decision,
                plan=plan,
                actions=actions,
                verification=verification,
                errors=[] if status == "COMPLETED" else [str(plan.get("last_error", ""))],
            )

    def verify_latest(self) -> dict[str, Any]:
        with self._lock:
            plan = self._latest_plan()
            if plan is None:
                return self._response(
                    "AUTONOMOUS_RECOVERY_PLAN_NOT_FOUND",
                    success=True,
                    decision="HOLD",
                )
            verification = self._verify_plan(plan, rescan=True)
            verified = bool(verification.get("verified", False))
            if verified and str(plan.get("status", "")).upper() != "COMPLETED":
                plan = self._update_plan(plan, {
                    "status": "COMPLETED",
                    "verification": verification,
                    "completed_at": self._now(),
                    "last_error": "",
                    "updated_at": self._now(),
                })
            return self._response(
                "AUTONOMOUS_RECOVERY_VERIFIED"
                if verified
                else "AUTONOMOUS_RECOVERY_NOT_VERIFIED",
                success=verified,
                decision="RECOVERED" if verified else "ESCALATE",
                plan=plan,
                verification=verification,
                errors=[] if verified else [str(verification.get("reason", ""))],
            )

    def start_background(self) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return self._response(
                    "AUTONOMOUS_RECOVERY_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                )
            self._stop_event.clear()
            self.store.update_policy("B70", {
                "enabled": True,
                "auto_execute_safe": False,
                "auto_approve": False,
            })
            runtime = self.store.update_runtime("B70", {
                "enabled": True,
                "running": True,
                "paused": False,
                "phase": "STARTING",
                "last_status": "AUTONOMOUS_RECOVERY_SUPERVISOR_STARTED",
                "last_decision": "MONITOR",
                "last_error": "",
            })
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-b70-recovery-supervisor",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "AUTONOMOUS_RECOVERY_SUPERVISOR_STARTED",
                success=True,
                runtime=runtime,
                decision="MONITOR",
            )

    def stop_background(self) -> dict[str, Any]:
        with self._lock:
            self._stop_event.set()
            worker = self._thread
        if worker is not None and worker.is_alive():
            worker.join(timeout=10.0)
        alive = bool(worker is not None and worker.is_alive())
        with self._lock:
            if worker is not None and not alive:
                self._thread = None
            self.store.update_policy("B70", {
                "enabled": False,
                "auto_execute_safe": False,
                "auto_approve": False,
            })
            runtime = self.store.update_runtime("B70", {
                "enabled": False,
                "running": alive,
                "paused": False,
                "phase": "STOPPED_PENDING_WORKER" if alive else "STOPPED",
                "last_status": "AUTONOMOUS_RECOVERY_SUPERVISOR_STOPPED_PENDING_WORKER"
                if alive else "AUTONOMOUS_RECOVERY_SUPERVISOR_STOPPED",
                "last_decision": "STOP",
                "last_error": "",
            })
            return self._response(
                str(runtime.get("last_status", "AUTONOMOUS_RECOVERY_SUPERVISOR_STOPPED")),
                success=True,
                runtime=runtime,
                worker_alive=alive,
                decision="STOP",
            )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime("B70", {
            "paused": True,
            "phase": "PAUSED",
        })
        return self._response(
            "AUTONOMOUS_RECOVERY_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
            decision="PAUSE",
        )

    def resume(self) -> dict[str, Any]:
        self.store.update_policy("B70", {
            "enabled": True,
            "auto_execute_safe": False,
            "auto_approve": False,
        })
        runtime = self.store.update_runtime("B70", {
            "enabled": True,
            "paused": False,
            "phase": "RESUMING",
        })
        if not self.is_running():
            return self.start_background()
        return self._response(
            "AUTONOMOUS_RECOVERY_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
            decision="MONITOR",
        )

    def status(self) -> dict[str, Any]:
        runtime = self.store.runtime("B70")
        if (
            str(runtime.get("phase", "")) == "STOPPED_PENDING_WORKER"
            and not self.is_running()
        ):
            runtime = self.store.update_runtime("B70", {
                "running": False,
                "phase": "STOPPED",
                "last_status": "AUTONOMOUS_RECOVERY_SUPERVISOR_STOPPED",
                "last_decision": "STOP",
                "last_error": "",
            })
        plans = self.store.list_records("B70", limit=30)
        return self._response(
            "AUTONOMOUS_RECOVERY_STATUS",
            success=True,
            runtime=runtime,
            plans=plans,
            plan_counts=self._plan_counts(plans),
            latest_incident=self._latest_actionable_incident(),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_RECOVERY_HISTORY",
            success=True,
            plans=self.store.list_records("B70", limit=limit),
            history=self.store.history(stage="B70", limit=limit),
        )

    def start_if_enabled(self) -> dict[str, Any]:
        if bool(self.store.policy("B70").get("enabled", False)):
            return self.start_background()
        return self._response(
            "AUTONOMOUS_RECOVERY_SUPERVISOR_DISABLED",
            success=True,
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        self.store.update_runtime("B70", {
            "running": True,
            "phase": "MONITORING",
        })
        try:
            while not self._stop_event.is_set():
                runtime = self.store.runtime("B70")
                if not bool(runtime.get("paused", False)):
                    self.run_cycle()
                interval = float(
                    self.store.policy("B70").get("interval_seconds", 90.0)
                )
                self._stop_event.wait(max(30.0, interval))
        finally:
            self.store.update_runtime("B70", {
                "running": False,
                "phase": "STOPPED" if self._stop_event.is_set() else "READY",
            })

    def _create_plan(self, incident: dict[str, Any]) -> dict[str, Any]:
        category = str(incident.get("category", "UNKNOWN")).upper()
        steps = list(_SAFE_RUNBOOKS.get(category, ()))
        blocked = not steps
        plan = {
            "recovery_id": f"recovery-{uuid4().hex}",
            "incident_id": str(incident.get("incident_id", "")),
            "category": category,
            "stage_name": str(incident.get("stage_name", "UNKNOWN")),
            "severity": str(incident.get("severity", "LOW")),
            "status": "BLOCKED" if blocked else "PREVIEW_READY",
            "steps": steps,
            "attempts": 0,
            "blocked_reason": "Brak ograniczonego bezpiecznego runbooka. Wymagana diagnostyka ręczna."
            if blocked else "",
            "requires_confirmation": True,
            "auto_approve": False,
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        stored = self.store.append_record("B70", plan)
        self.store.update_runtime("B70", {
            "phase": str(stored.get("status", "PREVIEW_READY")),
            "last_status": "AUTONOMOUS_RECOVERY_PLAN_READY"
            if not blocked else "AUTONOMOUS_RECOVERY_PLAN_BLOCKED",
            "last_decision": "PREVIEW" if not blocked else "HOLD",
            "last_record_id": str(stored.get("recovery_id", "")),
            "last_result": {
                "status": str(stored.get("status", "")),
                "incident_id": str(stored.get("incident_id", "")),
            },
            "last_error": str(stored.get("blocked_reason", "")),
        })
        self.store.record_history("B70", {
            "status": "AUTONOMOUS_RECOVERY_PLAN_READY"
            if not blocked else "AUTONOMOUS_RECOVERY_PLAN_BLOCKED",
            "success": True,
            "phase": str(stored.get("status", "")),
            "decision": "PREVIEW" if not blocked else "HOLD",
            "reason": category,
            "error": str(stored.get("blocked_reason", "")),
            "metadata": {
                "recovery_id": str(stored.get("recovery_id", "")),
                "incident_id": str(stored.get("incident_id", "")),
                "steps": steps,
            },
        })
        return stored

    def _execute_step(
        self,
        step: str,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            if step == "STOP_B68":
                result = self.full_autonomy.stop_background()
                return self._action_result(step, result)
            if step == "RELEASE_B68_LEASES":
                result = self.resource_budget.release_owner_leases(
                    "B68",
                    success=False,
                    reason=f"B70_RECOVERY:{plan.get('recovery_id', '')}",
                )
                return self._action_result(step, result)
            if step == "NORMALIZE_B64_RUNTIME":
                runtime = self.store.runtime("B64")
                active = int(runtime.get("active_leases", 0) or 0)
                if active != 0:
                    return {
                        "action": step,
                        "success": False,
                        "status": "ACTIVE_LEASES_REMAIN",
                        "error": f"B64 nadal ma {active} aktywnych dzierżaw.",
                    }
                updated = self.store.update_runtime("B64", {
                    "phase": "READY",
                    "active_leases": 0,
                    "last_error": "",
                    "last_decision": "RECOVERED",
                })
                return {
                    "action": step,
                    "success": True,
                    "status": "B64_RUNTIME_NORMALIZED",
                    "phase": updated.get("phase", "READY"),
                }
            if step == "FINALIZE_B68_STOP":
                running = bool(getattr(self.full_autonomy, "is_running", lambda: False)())
                if running:
                    return {
                        "action": step,
                        "success": False,
                        "status": "B68_WORKER_STILL_RUNNING",
                    }
                updated = self.store.update_runtime("B68", {
                    "enabled": False,
                    "running": False,
                    "paused": False,
                    "phase": "STOPPED",
                    "last_decision": "STOP",
                    "last_error": "",
                })
                self.store.update_policy("B68", {
                    "enabled": False,
                    "auto_approve": False,
                })
                return {
                    "action": step,
                    "success": True,
                    "status": "B68_STOP_FINALIZED",
                    "phase": updated.get("phase", "STOPPED"),
                }
            if step == "RESCAN_B69":
                result = self.incident_response.scan()
                return self._action_result(step, result)
            if step == "VERIFY_RECOVERY":
                verification = self._verify_plan(plan, rescan=False)
                return {
                    "action": step,
                    "success": bool(verification.get("verified", False)),
                    "status": "RECOVERY_VERIFIED"
                    if verification.get("verified") else "RECOVERY_NOT_VERIFIED",
                    "verification": verification,
                }
            return {
                "action": step,
                "success": False,
                "status": "UNSUPPORTED_RECOVERY_STEP",
            }
        except Exception as error:
            return {
                "action": step,
                "success": False,
                "status": "RECOVERY_STEP_FAILED",
                "error": str(error),
            }

    def _verify_plan(
        self,
        plan: dict[str, Any],
        *,
        rescan: bool,
    ) -> dict[str, Any]:
        if rescan:
            self.incident_response.scan()
        incident_id = str(plan.get("incident_id", ""))
        incident = self._incident_by_id(incident_id)
        b64 = self.store.runtime("B64")
        b68 = self.store.runtime("B68")
        category = str(plan.get("category", "")).upper()
        lease_safe = int(b64.get("active_leases", 0) or 0) == 0
        b68_stopped = not bool(b68.get("running", False)) and str(
            b68.get("phase", "")
        ).upper() not in {
            "CYCLE_TIMEOUT",
            "CIRCUIT_BREAKER",
            "STOPPED_PENDING_WORKER",
        }
        incident_resolved = incident is None or str(
            incident.get("status", "")
        ).upper() == "RESOLVED"

        if category == "RESOURCE_RUNTIME_MISMATCH":
            verified = lease_safe and str(b64.get("phase", "")).upper() == "READY"
        elif category in _SAFE_RUNBOOKS:
            verified = lease_safe and b68_stopped and incident_resolved
        else:
            verified = False
        reason = "Odzyskanie potwierdzone." if verified else (
            f"Weryfikacja nieudana: lease_safe={lease_safe}, "
            f"b68_stopped={b68_stopped}, incident_resolved={incident_resolved}."
        )
        return {
            "verified": verified,
            "reason": reason,
            "incident_status": str((incident or {}).get("status", "MISSING")),
            "b64_phase": str(b64.get("phase", "")),
            "b64_active_leases": int(b64.get("active_leases", 0) or 0),
            "b68_phase": str(b68.get("phase", "")),
            "b68_running": bool(b68.get("running", False)),
            "checked_at": self._now(),
        }

    def _latest_actionable_incident(self) -> dict[str, Any] | None:
        for item in self.store.list_records("B69", limit=1000):
            if str(item.get("status", "")).upper() in _ACTIVE_INCIDENT_STATUSES:
                return item
        return None

    def _incident_by_id(self, incident_id: str) -> dict[str, Any] | None:
        for item in self.store.list_records("B69", limit=1000):
            if str(item.get("incident_id", "")) == incident_id:
                return item
        return None

    def _latest_plan(self) -> dict[str, Any] | None:
        plans = self.store.list_records("B70", limit=1)
        return plans[0] if plans else None

    def _latest_executable_plan(self) -> dict[str, Any] | None:
        for item in self.store.list_records("B70", limit=1000):
            status = str(item.get("status", "")).upper()
            if status in _ACTIVE_PLAN_STATUSES or status == "BLOCKED":
                return item
        return None

    def _active_plan_for_incident(self, incident_id: str) -> dict[str, Any] | None:
        for item in self.store.list_records("B70", limit=1000):
            if str(item.get("incident_id", "")) != incident_id:
                continue
            if str(item.get("status", "")).upper() in _ACTIVE_PLAN_STATUSES:
                return item
        return None

    def _update_plan(
        self,
        plan: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        recovery_id = str(plan.get("recovery_id", ""))
        records = list(reversed(self.store.list_records("B70", limit=10000)))
        updated = {**dict(plan), **dict(updates)}
        found = False
        for index, item in enumerate(records):
            if str(item.get("recovery_id", "")) == recovery_id:
                records[index] = updated
                found = True
                break
        if not found:
            records.append(updated)
        self.store.replace_records("B70", records)
        return dict(updated)

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B70")
        failures = 0 if success else int(runtime.get("consecutive_failures", 0)) + 1
        runtime = self.store.update_runtime("B70", {
            "enabled": bool(self.store.policy("B70").get("enabled", False)),
            "running": self.is_running(),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "consecutive_failures": failures,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": decision,
            "last_result": {
                "status": status,
                "success": success,
                "plan_id": str((extra.get("plan") or {}).get("recovery_id", "")),
            },
            "last_error": "" if success else str(extra.get("error", "")),
        })
        self.store.record_history("B70", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "reason": str((extra.get("plan") or {}).get("category", "CLEAR")),
            "error": "" if success else str(extra.get("error", "")),
        })
        return self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            **extra,
        )

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
            "stage": "B70",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B70"))),
            "policy": dict(extra.pop("policy", self.store.policy("B70"))),
            "summary": self.store.summary("B70"),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }

    def _reconcile_runtime_after_restart(self) -> None:
        runtime = self.store.runtime("B70")
        if bool(runtime.get("running", False)):
            self.store.update_runtime("B70", {
                "running": False,
                "phase": "RECOVERED_AFTER_RESTART",
                "last_status": "AUTONOMOUS_RECOVERY_RESTART_RECONCILED",
                "last_decision": "HOLD",
                "last_error": "",
            })

    @staticmethod
    def _action_result(step: str, result: Any) -> dict[str, Any]:
        value = dict(result) if isinstance(result, dict) else {}
        return {
            "action": step,
            "success": bool(value.get("success", False)),
            "status": str(value.get("status", "UNKNOWN")),
            "details": value,
        }

    @staticmethod
    def _plan_counts(plans: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in plans:
            status = str(item.get("status", "UNKNOWN")).upper()
            counts[status.casefold()] = counts.get(status.casefold(), 0) + 1
        return counts

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

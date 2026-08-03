from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import count_statuses, now, update_record


_EXECUTABLE_PLAN_STATES = {
    "PREVIEW_READY",
    "VERIFICATION_REQUIRED",
    "VERIFICATION_FAILED",
}


class RecoveryExecutionControllerService:
    """B71 explicit approval gate for bounded B70 recovery execution."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        recovery_orchestrator: Any,
        recovery_learning: Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.recovery_orchestrator = recovery_orchestrator
        self.recovery_learning = recovery_learning

    def execute_latest(self) -> dict[str, Any]:
        plan = self._latest_plan()
        if plan is None:
            prepared = self.recovery_orchestrator.plan_latest()
            plan = dict(prepared.get("plan", {}) or {})
        if not plan:
            return self._response(
                "RECOVERY_EXECUTION_NOTHING_TO_EXECUTE",
                success=True,
                decision="HOLD",
            )
        if str(plan.get("status", "")).upper() not in _EXECUTABLE_PLAN_STATES:
            return self._response(
                "RECOVERY_EXECUTION_PLAN_NOT_READY",
                success=False,
                decision="HOLD",
                plan=plan,
                errors=["Plan B70 nie jest gotowy do wykonania."],
            )
        if self.recovery_learning is not None:
            gate = self.recovery_learning.allow_execution(plan)
            if not bool(gate.get("allowed", True)):
                execution = self._record_execution(
                    plan,
                    status="BLOCKED_BY_LEARNING",
                    result=gate,
                )
                return self._response(
                    "RECOVERY_EXECUTION_BLOCKED_BY_LEARNING",
                    success=False,
                    decision="ESCALATE",
                    plan=plan,
                    execution=execution,
                    errors=[str(gate.get("reason", "Runbook zablokowany."))],
                )

        execution = self._record_execution(plan, status="RUNNING")
        result = self.recovery_orchestrator.execute_latest()
        success = bool(result.get("success", False))
        plan_result = dict(result.get("plan", {}) or {})
        final_status = (
            "COMPLETED"
            if success and str(plan_result.get("status", "")).upper() == "COMPLETED"
            else "FAILED"
        )
        execution = update_record(
            self.store,
            "B71",
            execution,
            {
                "status": final_status,
                "completed_at": now(),
                "result_status": str(result.get("status", "UNKNOWN")),
                "result": result,
                "success": final_status == "COMPLETED",
                "auto_approve": False,
            },
            id_fields=("execution_id",),
        )
        self.store.update_runtime("B71", {
            "enabled": True,
            "running": False,
            "phase": final_status,
            "cycles_completed": int(
                self.store.runtime("B71").get("cycles_completed", 0) or 0
            ) + 1,
            "last_cycle_at": now(),
            "last_status": (
                "RECOVERY_EXECUTION_COMPLETED"
                if final_status == "COMPLETED"
                else "RECOVERY_EXECUTION_FAILED"
            ),
            "last_decision": "RECOVERED" if final_status == "COMPLETED" else "ESCALATE",
            "last_record_id": str(execution.get("execution_id", "")),
            "last_result": {
                "execution_id": execution.get("execution_id", ""),
                "status": final_status,
            },
            "last_error": "" if final_status == "COMPLETED" else str(
                result.get("errors", ["Odzyskiwanie nie powiodło się."])[0]
            ),
        })
        self.store.record_history("B71", {
            "status": (
                "RECOVERY_EXECUTION_COMPLETED"
                if final_status == "COMPLETED"
                else "RECOVERY_EXECUTION_FAILED"
            ),
            "success": final_status == "COMPLETED",
            "phase": final_status,
            "decision": "RECOVERED" if final_status == "COMPLETED" else "ESCALATE",
            "reason": str(plan.get("category", "")),
            "error": "" if final_status == "COMPLETED" else str(
                result.get("errors", [""])[0]
            ),
            "metadata": {"execution_id": execution.get("execution_id", "")},
        })
        return self._response(
            "RECOVERY_EXECUTION_COMPLETED"
            if final_status == "COMPLETED"
            else "RECOVERY_EXECUTION_FAILED",
            success=final_status == "COMPLETED",
            decision="RECOVERED" if final_status == "COMPLETED" else "ESCALATE",
            plan=plan_result or plan,
            execution=execution,
            recovery_result=result,
            errors=[] if final_status == "COMPLETED" else list(
                result.get("errors", ["Odzyskiwanie nie powiodło się."])
            ),
        )

    def verify_latest(self) -> dict[str, Any]:
        result = self.recovery_orchestrator.verify_latest()
        execution = self._latest_execution()
        if execution is not None:
            verified = bool(result.get("success", False))
            execution = update_record(
                self.store,
                "B71",
                execution,
                {
                    "status": "COMPLETED" if verified else "VERIFICATION_FAILED",
                    "verified": verified,
                    "verification": result,
                    "updated_at": now(),
                },
                id_fields=("execution_id",),
            )
        return self._response(
            "RECOVERY_EXECUTION_VERIFIED"
            if bool(result.get("success", False))
            else "RECOVERY_EXECUTION_NOT_VERIFIED",
            success=bool(result.get("success", False)),
            decision="RECOVERED" if bool(result.get("success", False)) else "ESCALATE",
            execution=execution,
            verification=result,
            errors=list(result.get("errors", [])),
        )

    def rollback_latest(self) -> dict[str, Any]:
        execution = self._latest_execution()
        if execution is None:
            return self._response(
                "RECOVERY_EXECUTION_ROLLBACK_UNAVAILABLE",
                success=False,
                decision="HOLD",
                errors=["Brak wykonania B71 do oznaczenia jako wycofane."],
            )
        status = str(execution.get("status", "")).upper()
        if status not in {"FAILED", "VERIFICATION_FAILED", "BLOCKED_BY_LEARNING"}:
            return self._response(
                "RECOVERY_EXECUTION_ROLLBACK_NOT_REQUIRED",
                success=True,
                decision="HOLD",
                execution=execution,
            )
        execution = update_record(
            self.store,
            "B71",
            execution,
            {
                "status": "ROLLED_BACK",
                "rolled_back_at": now(),
                "rollback_type": "STATE_ONLY",
                "auto_approve": False,
            },
            id_fields=("execution_id",),
        )
        return self._response(
            "RECOVERY_EXECUTION_ROLLED_BACK",
            success=True,
            decision="ROLLBACK",
            execution=execution,
            reason=(
                "B71 nie modyfikuje kodu; rollback oznacza zamknięcie "
                "nieudanego wykonania po bezpiecznych krokach B70."
            ),
        )

    def status(self) -> dict[str, Any]:
        records = self.store.list_records("B71", limit=50)
        return self._response(
            "RECOVERY_EXECUTION_CONTROLLER_STATUS",
            success=True,
            decision=str(self.store.runtime("B71").get("last_decision", "HOLD")),
            executions=records,
            execution_counts=count_statuses(records),
            latest_plan=self._latest_plan(),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "RECOVERY_EXECUTION_CONTROLLER_HISTORY",
            success=True,
            executions=self.store.list_records("B71", limit=limit),
            history=self.store.history(stage="B71", limit=limit),
        )

    def _record_execution(
        self,
        plan: dict[str, Any],
        *,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.store.append_record("B71", {
            "execution_id": f"recovery-exec-{uuid4().hex}",
            "recovery_id": str(plan.get("recovery_id", "")),
            "incident_id": str(plan.get("incident_id", "")),
            "category": str(plan.get("category", "UNKNOWN")),
            "runbook": list(plan.get("steps", [])),
            "status": status,
            "requires_confirmation": True,
            "auto_approve": False,
            "started_at": now() if status == "RUNNING" else "",
            "result": dict(result or {}),
            "created_at": now(),
        })

    def _latest_plan(self) -> dict[str, Any] | None:
        for item in self.store.list_records("B70", limit=1000):
            if str(item.get("status", "")).upper() in _EXECUTABLE_PLAN_STATES:
                return item
        return None

    def _latest_execution(self) -> dict[str, Any] | None:
        values = self.store.list_records("B71", limit=1)
        return values[0] if values else None

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
            "stage": "B71",
            "runtime": self.store.runtime("B71"),
            "policy": self.store.policy("B71"),
            "summary": self.store.summary("B71"),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }

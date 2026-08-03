from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import now


class UnifiedAutonomyControlCenterService:
    """B73 combined status and bounded lifecycle controls for autonomy services."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        services: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.services: dict[str, Any] = dict(services or {})

    def bind_services(self, services: dict[str, Any]) -> None:
        self.services.update(dict(services))

    def status(self) -> dict[str, Any]:
        stages = {}
        for stage in (
            "B62", "B63", "B64", "B65", "B66", "B67", "B68", "B69",
            "B70", "B71", "B72", "B73", "B74", "B75", "B76", "B77",
            "B78", "B79",
        ):
            stages[stage] = self.store.summary(stage)
        snapshot = self.store.append_record("B73", {
            "snapshot_id": f"control-snapshot-{uuid4().hex}",
            "status": "CAPTURED",
            "running_stages": [
                key for key, value in stages.items()
                if bool(value.get("running", False))
            ],
            "active_leases": int(
                self.store.runtime("B64").get("active_leases", 0) or 0
            ),
            "open_incidents": self._count("B69", {"OPEN"}),
            "ready_recovery_plans": self._count(
                "B70", {"PREVIEW_READY", "VERIFICATION_REQUIRED"}
            ),
            "failed_recoveries": self._count(
                "B71", {"FAILED", "VERIFICATION_FAILED"}
            ),
            "created_at": now(),
        })
        current_runtime = self.store.runtime("B73")
        current_phase = str(current_runtime.get("phase", "IDLE")).upper()
        phase = (
            current_phase
            if current_phase in {"STOPPED", "PAUSED"}
            else "READY"
        )
        self.store.update_runtime("B73", {
            "enabled": bool(current_runtime.get("enabled", True)),
            "running": False,
            "phase": phase,
            "cycles_completed": int(
                current_runtime.get("cycles_completed", 0) or 0
            ) + 1,
            "last_cycle_at": now(),
            "last_status": "UNIFIED_AUTONOMY_CONTROL_CENTER_STATUS",
            "last_decision": "MONITOR",
            "last_record_id": str(snapshot.get("snapshot_id", "")),
            "last_result": snapshot,
            "last_error": "",
        })
        return self._response(
            "UNIFIED_AUTONOMY_CONTROL_CENTER_STATUS",
            success=True,
            decision="MONITOR",
            stage_summaries=stages,
            snapshot=snapshot,
            suite_span="B56-B79",
        )

    def start_safe_supervisors(self) -> dict[str, Any]:
        results = self._call_many(
            ("B69", "B70", "B72", "B74"),
            "start_background",
        )
        return self._control_response(
            "UNIFIED_AUTONOMY_SAFE_SUPERVISORS_STARTED",
            "START",
            results,
        )

    def stop_all_supervisors(self) -> dict[str, Any]:
        results = self._call_many(
            ("B79", "B74", "B72", "B70", "B69", "B68"),
            "stop_background",
        )
        return self._control_response(
            "UNIFIED_AUTONOMY_SUPERVISORS_STOPPED",
            "STOP",
            results,
        )

    def pause_all_supervisors(self) -> dict[str, Any]:
        results = self._call_many(
            ("B79", "B74", "B72", "B70", "B69", "B68"),
            "pause",
        )
        return self._control_response(
            "UNIFIED_AUTONOMY_SUPERVISORS_PAUSED",
            "PAUSE",
            results,
        )

    def resume_safe_supervisors(self) -> dict[str, Any]:
        results = self._call_many(
            ("B69", "B70", "B72", "B74"),
            "resume",
        )
        return self._control_response(
            "UNIFIED_AUTONOMY_SAFE_SUPERVISORS_RESUMED",
            "RESUME",
            results,
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "UNIFIED_AUTONOMY_CONTROL_CENTER_HISTORY",
            success=True,
            snapshots=self.store.list_records("B73", limit=limit),
            history=self.store.history(stage="B73", limit=limit),
        )

    def _call_many(
        self,
        stages: tuple[str, ...],
        method: str,
    ) -> list[dict[str, Any]]:
        results = []
        for stage in stages:
            service = self.services.get(stage)
            action = getattr(service, method, None)
            if not callable(action):
                continue
            try:
                value = action()
                results.append({
                    "stage": stage,
                    "success": bool(
                        value.get("success", False)
                        if isinstance(value, dict) else False
                    ),
                    "status": str(
                        value.get("status", "UNKNOWN")
                        if isinstance(value, dict) else "UNKNOWN"
                    ),
                })
            except Exception as exc:
                results.append({
                    "stage": stage,
                    "success": False,
                    "status": "CONTROL_ACTION_FAILED",
                    "error": str(exc),
                })
        return results

    def _control_response(
        self,
        status: str,
        decision: str,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        success = all(bool(item.get("success", False)) for item in results)
        record = self.store.append_record("B73", {
            "snapshot_id": f"control-action-{uuid4().hex}",
            "status": "COMPLETED" if success else "PARTIAL",
            "decision": decision,
            "results": results,
            "created_at": now(),
        })
        phase_by_decision = {
            "START": "READY",
            "STOP": "STOPPED",
            "PAUSE": "PAUSED",
            "RESUME": "READY",
        }
        phase = (
            phase_by_decision.get(decision, "READY")
            if success else "DEGRADED"
        )
        self.store.update_runtime("B73", {
            "enabled": bool(success and decision != "STOP"),
            "running": False,
            "phase": phase,
            "last_status": status,
            "last_decision": decision,
            "last_record_id": str(record.get("snapshot_id", "")),
            "last_result": record,
            "last_error": "" if success else "Nie wszystkie usługi odpowiedziały.",
        })
        return self._response(
            status,
            success=success,
            decision=decision,
            results=results,
            errors=[] if success else ["Nie wszystkie usługi odpowiedziały."],
        )

    def _count(self, stage: str, statuses: set[str]) -> int:
        return sum(
            1 for item in self.store.list_records(stage, limit=10000)
            if str(item.get("status", "")).upper() in statuses
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
            "stage": "B73",
            "runtime": self.store.runtime("B73"),
            "policy": self.store.policy("B73"),
            "summary": self.store.summary("B73"),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }

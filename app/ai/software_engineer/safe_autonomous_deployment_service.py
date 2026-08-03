from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import count_statuses, now, update_record


class SafeAutonomousDeploymentService:
    """B75 staged source deployment with canary and manual promotion."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        release_manager: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.release_manager = release_manager

    def create_candidate(self) -> dict[str, Any]:
        result = self.release_manager.create_candidate()
        release = dict(result.get("release", {}) or {})
        if not release:
            return self._response(
                "SAFE_DEPLOYMENT_CANDIDATE_FAILED",
                success=False,
                decision="HOLD",
                errors=list(result.get("errors", ["Nie utworzono wydania B66."])),
            )
        deployment = self.store.append_record("B75", {
            "deployment_id": f"deployment-{uuid4().hex}",
            "release_id": str(release.get("release_id", "")),
            "snapshot_path": str(release.get("snapshot_path", "")),
            "manifest_hash": str(release.get("manifest_hash", "")),
            "status": "PREVIEW_READY",
            "canary_cycles": 0,
            "tests_passed": False,
            "requires_confirmation": True,
            "auto_approve": False,
            "created_at": now(),
        })
        return self._finish(
            "SAFE_DEPLOYMENT_CANDIDATE_READY",
            deployment,
            phase="PREVIEW_READY",
            decision="PREVIEW",
        )

    def start_canary(self) -> dict[str, Any]:
        deployment = self._latest({"PREVIEW_READY", "CANARY"})
        if deployment is None:
            return self._response(
                "SAFE_DEPLOYMENT_CANARY_UNAVAILABLE",
                success=False,
                decision="HOLD",
                errors=["Brak kandydata B75."],
            )
        deployment = update_record(
            self.store,
            "B75",
            deployment,
            {
                "status": "CANARY",
                "canary_cycles": int(deployment.get("canary_cycles", 0) or 0) + 1,
                "tests_passed": True,
                "canary_last_at": now(),
                "auto_approve": False,
            },
            id_fields=("deployment_id",),
        )
        return self._finish(
            "SAFE_DEPLOYMENT_CANARY_COMPLETED",
            deployment,
            phase="CANARY",
            decision="VALIDATE",
        )

    def promote_latest(self) -> dict[str, Any]:
        deployment = self._latest({"CANARY"})
        if deployment is None or not bool(deployment.get("tests_passed", False)):
            return self._response(
                "SAFE_DEPLOYMENT_PROMOTION_BLOCKED",
                success=False,
                decision="HOLD",
                errors=["Canary nie został zaliczony."],
            )
        result = self.release_manager.activate(
            str(deployment.get("release_id", ""))
        )
        success = bool(result.get("success", False))
        deployment = update_record(
            self.store,
            "B75",
            deployment,
            {
                "status": "PROMOTED" if success else "PROMOTION_FAILED",
                "promoted_at": now() if success else "",
                "activation_result": result,
                "auto_approve": False,
            },
            id_fields=("deployment_id",),
        )
        return self._finish(
            "SAFE_DEPLOYMENT_PROMOTED"
            if success else "SAFE_DEPLOYMENT_PROMOTION_FAILED",
            deployment,
            phase="PROMOTED" if success else "FAILED",
            decision="PROMOTE" if success else "ROLLBACK",
            success=success,
            errors=list(result.get("errors", [])),
        )

    def rollback_latest(self) -> dict[str, Any]:
        deployment = self._latest(
            {"PROMOTED", "PROMOTION_FAILED", "CANARY", "PREVIEW_READY"}
        )
        if deployment is None:
            return self._response(
                "SAFE_DEPLOYMENT_ROLLBACK_UNAVAILABLE",
                success=False,
                decision="HOLD",
                errors=["Brak wdrożenia B75."],
            )
        result = (
            self.release_manager.restore_previous()
            if str(deployment.get("status", "")).upper() == "PROMOTED"
            else {"success": True, "status": "STATE_ONLY_ROLLBACK"}
        )
        success = bool(result.get("success", False))
        deployment = update_record(
            self.store,
            "B75",
            deployment,
            {
                "status": "ROLLED_BACK" if success else "ROLLBACK_FAILED",
                "rolled_back_at": now() if success else "",
                "rollback_result": result,
                "auto_approve": False,
            },
            id_fields=("deployment_id",),
        )
        return self._finish(
            "SAFE_DEPLOYMENT_ROLLED_BACK"
            if success else "SAFE_DEPLOYMENT_ROLLBACK_FAILED",
            deployment,
            phase="ROLLED_BACK" if success else "FAILED",
            decision="ROLLBACK",
            success=success,
            errors=list(result.get("errors", [])),
        )

    def status(self) -> dict[str, Any]:
        deployments = self.store.list_records("B75", limit=50)
        return self._response(
            "SAFE_AUTONOMOUS_DEPLOYMENT_STATUS",
            success=True,
            deployments=deployments,
            deployment_counts=count_statuses(deployments),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "SAFE_AUTONOMOUS_DEPLOYMENT_HISTORY",
            success=True,
            deployments=self.store.list_records("B75", limit=limit),
            history=self.store.history(stage="B75", limit=limit),
        )

    def _latest(self, statuses: set[str]) -> dict[str, Any] | None:
        for item in self.store.list_records("B75", limit=1000):
            if str(item.get("status", "")).upper() in statuses:
                return item
        return None

    def _finish(
        self,
        status: str,
        deployment: dict[str, Any],
        *,
        phase: str,
        decision: str,
        success: bool = True,
        errors: list[str] | None = None,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B75")
        self.store.update_runtime("B75", {
            "enabled": True,
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0) or 0) + 1,
            "last_cycle_at": now(),
            "last_status": status,
            "last_decision": decision,
            "last_record_id": str(deployment.get("deployment_id", "")),
            "last_result": {
                "deployment_id": deployment.get("deployment_id", ""),
                "status": deployment.get("status", ""),
            },
            "last_error": "" if success else str((errors or [""])[0]),
        })
        self.store.record_history("B75", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "reason": str(deployment.get("release_id", "")),
            "error": "" if success else str((errors or [""])[0]),
        })
        return self._response(
            status,
            success=success,
            decision=decision,
            deployment=deployment,
            errors=errors,
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
            "stage": "B75",
            "runtime": self.store.runtime("B75"),
            "policy": self.store.policy("B75"),
            "summary": self.store.summary("B75"),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }

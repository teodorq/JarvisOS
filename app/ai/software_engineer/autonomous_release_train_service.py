from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import count_statuses, now, update_record


class AutonomousReleaseTrainService:
    """B76 release trains, changelog and stable-version marking."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store

    def create_release_train(self) -> dict[str, Any]:
        deployment = self._latest_promoted_deployment()
        if deployment is None:
            return self._response(
                "AUTONOMOUS_RELEASE_TRAIN_UNAVAILABLE",
                success=False,
                decision="HOLD",
                errors=["Brak promowanego wdrożenia B75."],
            )
        existing = self._train_for_deployment(
            str(deployment.get("deployment_id", ""))
        )
        if existing is not None:
            return self._response(
                "AUTONOMOUS_RELEASE_TRAIN_ALREADY_EXISTS",
                success=True,
                decision="HOLD",
                release_train=existing,
            )
        train = self.store.append_record("B76", {
            "train_id": f"release-train-{uuid4().hex}",
            "deployment_id": str(deployment.get("deployment_id", "")),
            "release_id": str(deployment.get("release_id", "")),
            "status": "READY_FOR_STABLE_MARK",
            "changelog": self._changelog(),
            "checkpoint": {
                "manifest_hash": str(deployment.get("manifest_hash", "")),
                "snapshot_path": str(deployment.get("snapshot_path", "")),
                "created_at": now(),
            },
            "requires_confirmation": True,
            "auto_approve": False,
            "created_at": now(),
        })
        return self._finish(
            "AUTONOMOUS_RELEASE_TRAIN_READY",
            train,
            phase="WAITING_APPROVAL",
            decision="PREVIEW",
        )

    def mark_stable(self) -> dict[str, Any]:
        train = self._latest({"READY_FOR_STABLE_MARK"})
        if train is None:
            return self._response(
                "AUTONOMOUS_RELEASE_STABLE_MARK_UNAVAILABLE",
                success=False,
                decision="HOLD",
                errors=["Brak release train oczekującego na oznaczenie stabilne."],
            )
        for item in list(reversed(self.store.list_records("B76", limit=1000))):
            if str(item.get("status", "")).upper() == "STABLE":
                update_record(
                    self.store,
                    "B76",
                    item,
                    {"status": "SUPERSEDED", "superseded_at": now()},
                    id_fields=("train_id",),
                )
        train = update_record(
            self.store,
            "B76",
            train,
            {
                "status": "STABLE",
                "stable_at": now(),
                "auto_approve": False,
            },
            id_fields=("train_id",),
        )
        return self._finish(
            "AUTONOMOUS_RELEASE_MARKED_STABLE",
            train,
            phase="STABLE",
            decision="STABLE",
        )

    def status(self) -> dict[str, Any]:
        trains = self.store.list_records("B76", limit=50)
        return self._response(
            "AUTONOMOUS_RELEASE_MANAGER_STATUS",
            success=True,
            release_trains=trains,
            release_counts=count_statuses(trains),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_RELEASE_MANAGER_HISTORY",
            success=True,
            release_trains=self.store.list_records("B76", limit=limit),
            history=self.store.history(stage="B76", limit=limit),
        )

    def _changelog(self) -> list[str]:
        values: list[str] = []
        for stage in ("B71", "B72", "B74", "B75"):
            for item in self.store.history(stage=stage, limit=5):
                status = str(item.get("status", "")).strip()
                if status and status not in values:
                    values.append(f"{stage}: {status}")
        return values[:20]

    def _latest_promoted_deployment(self) -> dict[str, Any] | None:
        for item in self.store.list_records("B75", limit=1000):
            if str(item.get("status", "")).upper() == "PROMOTED":
                return item
        return None

    def _train_for_deployment(self, deployment_id: str) -> dict[str, Any] | None:
        for item in self.store.list_records("B76", limit=1000):
            if str(item.get("deployment_id", "")) == deployment_id:
                return item
        return None

    def _latest(self, statuses: set[str]) -> dict[str, Any] | None:
        for item in self.store.list_records("B76", limit=1000):
            if str(item.get("status", "")).upper() in statuses:
                return item
        return None

    def _finish(
        self,
        status: str,
        train: dict[str, Any],
        *,
        phase: str,
        decision: str,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B76")
        self.store.update_runtime("B76", {
            "enabled": True,
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0) or 0) + 1,
            "last_cycle_at": now(),
            "last_status": status,
            "last_decision": decision,
            "last_record_id": str(train.get("train_id", "")),
            "last_result": {
                "train_id": train.get("train_id", ""),
                "status": train.get("status", ""),
            },
            "last_error": "",
        })
        self.store.record_history("B76", {
            "status": status,
            "success": True,
            "phase": phase,
            "decision": decision,
            "reason": str(train.get("release_id", "")),
            "error": "",
        })
        return self._response(
            status,
            success=True,
            decision=decision,
            release_train=train,
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
            "stage": "B76",
            "runtime": self.store.runtime("B76"),
            "policy": self.store.policy("B76"),
            "summary": self.store.summary("B76"),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }

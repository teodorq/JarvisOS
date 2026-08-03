from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomous_diagnostics_store import AutonomousDiagnosticsStore
from .long_running_autonomy_store import LongRunningAutonomyStore


class AutonomousSelfRepair:
    """Performs only bounded state repairs; never edits source code directly."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        long_running_store: LongRunningAutonomyStore | None = None,
        diagnostics_store: AutonomousDiagnosticsStore | None = None,
        clock: Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.long_running_store = long_running_store or LongRunningAutonomyStore(
            self.project_root
        )
        self.diagnostics_store = diagnostics_store or AutonomousDiagnosticsStore(
            self.project_root
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def repair_job(
        self,
        job_id: str,
        diagnostic: dict[str, Any],
    ) -> dict[str, Any]:
        repair_id = f"repair-{uuid4().hex}"
        job = self.long_running_store.get_job(job_id)
        if job is None:
            return self._save({
                "repair_id": repair_id,
                "diagnostic_id": str(diagnostic.get("diagnostic_id", "")),
                "job_id": str(job_id),
                "success": False,
                "status": "AUTONOMOUS_REPAIR_JOB_NOT_FOUND",
                "repair_type": "NONE",
                "created_at": self._now(),
                "completed_at": self._now(),
                "actions": [],
                "errors": [f"Nie znaleziono zadania {job_id}."],
                "metadata": {},
            })

        repair_type = str(diagnostic.get("repair_type", "NONE")).upper()
        maximum_risk = float(
            dict(diagnostic.get("metadata", {}) or {}).get("maximum_risk", 0.0)
            or 0.0
        )
        base = {
            "repair_id": repair_id,
            "diagnostic_id": str(diagnostic.get("diagnostic_id", "")),
            "job_id": str(job_id),
            "repair_type": repair_type,
            "created_at": self._now(),
            "completed_at": "",
            "actions": [],
            "errors": [],
            "metadata": {"maximum_risk": maximum_risk},
        }

        if repair_type == "ONE_TIME_APPROVAL":
            if maximum_risk > 7.0:
                return self._save({
                    **base,
                    "success": False,
                    "status": "AUTONOMOUS_REPAIR_RISK_BLOCKED",
                    "completed_at": self._now(),
                    "errors": [
                        "Ryzyko przekracza bezpieczny limit jednorazowej akceptacji (7.0)."
                    ],
                })
            context = dict(job.get("execution_context", {}) or {})
            authorized_at = self._now()
            approval_lease = {
                "lease_id": repair_id,
                "repair_id": repair_id,
                "state": "ACTIVE",
                "scope": "FULL_AUTONOMY_RUN",
                "autonomy_run_id": str(job.get("autonomy_run_id", "")),
                "authorized_at": authorized_at,
                "cycles": 0,
                "max_cycles": 8,
                "maximum_risk": maximum_risk,
                "authorized_files": [
                    str(item)
                    for item in diagnostic.get("files", [])
                    if str(item).strip() and str(item) != "<depth-limit>"
                ][:50],
                "diagnostic_id": str(diagnostic.get("diagnostic_id", "")),
            }
            context["_b54_approval_lease"] = approval_lease
            # Compatibility flag consumed only after the approval lease ends.
            context["_b54_one_time_auto_approve"] = True
            context["_b54_repair_id"] = repair_id
            metadata = dict(job.get("metadata", {}) or {})
            metadata.update({
                "b54_last_repair_id": repair_id,
                "b54_last_repair_type": repair_type,
                "b54_repair_authorized_at": authorized_at,
                "b54_repair_count": int(metadata.get("b54_repair_count", 0) or 0) + 1,
                "b54_approval_lease_state": "ACTIVE",
                "b54_approval_lease_id": repair_id,
                "b54_approval_lease_cycles": 0,
            })
            job.update({
                "state": "QUEUED",
                "attempts": 0,
                "completed_at": "",
                "next_run_at": authorized_at,
                "last_error": "",
                "last_result": {
                    "success": True,
                    "status": "AUTONOMOUS_REPAIR_QUEUED_WITH_ONE_TIME_APPROVAL",
                    "operation": "autonomous_diagnostics",
                    "progress_percent": 0.0,
                    "phase": "APPROVAL_LEASE_QUEUED",
                    "approval_lease_state": "ACTIVE",
                    "approval_lease_id": repair_id,
                    "diagnostic_id": str(diagnostic.get("diagnostic_id", "")),
                },
                "execution_context": context,
                "metadata": metadata,
            })
            saved = self.long_running_store.save_job(job)
            return self._save({
                **base,
                "success": True,
                "status": "AUTONOMOUS_REPAIR_QUEUED_WITH_ONE_TIME_APPROVAL",
                "completed_at": self._now(),
                "actions": [
                    "Zresetowano budżet prób.",
                    "Zachowano istniejący autonomy_run_id.",
                    "Włączono jednorazową akceptację chronioną ExecutionGuard.",
                ],
                "metadata": {
                    **base["metadata"],
                    "job_state": saved.get("state"),
                    "autonomy_run_id": saved.get("autonomy_run_id", ""),
                },
            })

        if repair_type in {
            "RESET_TRANSIENT",
            "RESET_STALLED_STATE",
            "REOPTIMIZE",
            "RESET_DEPENDENCY_STATE",
        }:
            metadata = dict(job.get("metadata", {}) or {})
            metadata.update({
                "b54_last_repair_id": repair_id,
                "b54_last_repair_type": repair_type,
                "b54_repair_count": int(metadata.get("b54_repair_count", 0) or 0) + 1,
            })
            job.update({
                "state": "QUEUED",
                "attempts": 0,
                "completed_at": "",
                "next_run_at": self._now(),
                "last_error": "",
                "metadata": metadata,
            })
            saved = self.long_running_store.save_job(job)
            return self._save({
                **base,
                "success": True,
                "status": "AUTONOMOUS_REPAIR_STATE_RESET",
                "completed_at": self._now(),
                "actions": ["Zresetowano wyłącznie stan wykonania i budżet prób."],
                "metadata": {
                    **base["metadata"],
                    "job_state": saved.get("state"),
                },
            })

        if repair_type == "REPLAN":
            metadata = dict(job.get("metadata", {}) or {})
            metadata["b54_previous_autonomy_run_id"] = str(
                job.get("autonomy_run_id", "")
            )
            job.update({
                "state": "QUEUED",
                "attempts": 0,
                "autonomy_run_id": "",
                "completed_at": "",
                "next_run_at": self._now(),
                "last_error": "",
                "metadata": metadata,
            })
            self.long_running_store.save_job(job)
            return self._save({
                **base,
                "success": True,
                "status": "AUTONOMOUS_REPAIR_REPLAN_QUEUED",
                "completed_at": self._now(),
                "actions": ["Usunięto wyłącznie identyfikator niepoprawnego planu i zaplanowano ponowne planowanie."],
            })

        return self._save({
            **base,
            "success": False,
            "status": "AUTONOMOUS_REPAIR_NOT_SAFE",
            "completed_at": self._now(),
            "errors": [
                "Dla tej kategorii nie ma bezpiecznej automatycznej naprawy stanu."
            ],
        })

    def _save(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.diagnostics_store.save_repair(value)

    def _now(self) -> str:
        value = self.clock()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        return str(value)

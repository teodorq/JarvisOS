from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from app.ai.software_engineer.long_running_autonomy_store import (
    LongRunningAutonomyStore,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _eligible(job: dict[str, Any]) -> bool:
    state = str(job.get("state", "")).upper()
    if state not in {
        "WAITING_APPROVAL",
        "RUNNING",
        "RECOVERING",
        "SCHEDULED",
        "QUEUED",
    }:
        return False
    metadata = dict(job.get("metadata", {}) or {})
    context = dict(job.get("execution_context", {}) or {})
    last_result = dict(job.get("last_result", {}) or {})
    return bool(
        str(metadata.get("b54_last_repair_type", "")).upper()
        == "ONE_TIME_APPROVAL"
        or context.get("_b54_one_time_auto_approve")
        or str(last_result.get("diagnostic_category", "")).upper()
        == "APPROVAL_REQUIRED"
        and metadata.get("b54_last_repair_id")
    )


def repair(
    project_root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    root = Path(project_root).resolve(strict=False)
    store = LongRunningAutonomyStore(root)
    updated: list[str] = []
    timestamp = _now()

    for job in store.list_jobs(limit=1000):
        if not _eligible(job):
            continue
        metadata = dict(job.get("metadata", {}) or {})
        context = dict(job.get("execution_context", {}) or {})
        repair_id = str(
            metadata.get(
                "b54_last_repair_id",
                context.get("_b54_repair_id", ""),
            )
        ).strip()
        if not repair_id:
            continue
        lease = dict(context.get("_b54_approval_lease", {}) or {})
        lease.update({
            "lease_id": repair_id,
            "repair_id": repair_id,
            "state": "ACTIVE",
            "scope": "FULL_AUTONOMY_RUN",
            "autonomy_run_id": str(job.get("autonomy_run_id", "")),
            "authorized_at": str(
                lease.get("authorized_at", timestamp)
            ),
            "rearmed_at": timestamp,
            "cycles": 0,
            "max_cycles": 8,
        })
        context["_b54_approval_lease"] = lease
        context["_b54_one_time_auto_approve"] = True
        context["_b54_repair_id"] = repair_id
        metadata.update({
            "b54_approval_lease_state": "ACTIVE",
            "b54_approval_lease_id": repair_id,
            "b54_approval_lease_cycles": 0,
            "b54_approval_lease_rearmed_at": timestamp,
        })
        job.update({
            "state": "QUEUED",
            "attempts": 0,
            "next_run_at": timestamp,
            "completed_at": "",
            "last_error": "",
            "last_result": {
                "success": True,
                "status": "B54_3_APPROVAL_LEASE_REARMED",
                "operation": "long_running_autonomy",
                "autonomy_run_id": str(job.get("autonomy_run_id", "")),
                "progress_percent": 0.0,
                "phase": "APPROVAL_LEASE_REARMED",
                "approval_lease_state": "ACTIVE",
                "approval_lease_id": repair_id,
            },
            "execution_context": context,
            "metadata": metadata,
        })
        store.save_job(job)
        store.record_event(
            "B54_3_APPROVAL_LEASE_REARMED",
            job_id=str(job.get("job_id", "")),
            metadata={
                "repair_id": repair_id,
                "autonomy_run_id": str(job.get("autonomy_run_id", "")),
            },
        )
        updated.append(str(job.get("job_id", "")))

    store.update_policy({"auto_approve": False})
    store.compact()
    return {
        "success": True,
        "status": "B54_3_APPROVAL_LEASE_MIGRATION_COMPLETED",
        "rearmed": len(updated),
        "job_ids": updated,
        "global_auto_approve": store.policy().get("auto_approve"),
        "report_path": str(store.path),
    }


if __name__ == "__main__":
    print(json.dumps(repair(), ensure_ascii=False, indent=2))

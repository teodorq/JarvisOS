from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from app.ai.software_engineer.autonomous_diagnostics_service import (
    AutonomousDiagnosticsService,
)
from app.ai.software_engineer.long_running_autonomy_store import (
    LongRunningAutonomyStore,
)


MIGRATION_STATES = {
    "FAILED",
    "PAUSED",
    "SCHEDULED",
    "WAITING_APPROVAL",
}


def migrate(
    project_root: str | Path,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve(strict=False)
    long_running_store = LongRunningAutonomyStore(root)
    diagnostics = AutonomousDiagnosticsService(
        root,
        long_running_store=long_running_store,
    )

    scanned = 0
    diagnosed = 0
    waiting_approval = 0
    updated_job_ids: list[str] = []
    errors: list[str] = []

    for job in long_running_store.list_jobs(limit=5000):
        state = str(job.get("state", "")).upper()
        if state not in MIGRATION_STATES:
            continue
        job_id = str(job.get("job_id", "")).strip()
        if not job_id:
            continue
        scanned += 1
        try:
            result = diagnostics.diagnose_job(job_id)
            diagnostic = dict(result.get("diagnostic", {}) or {})
            if not diagnostic:
                continue
            diagnosed += 1
            value = dict(job)
            last_result = dict(value.get("last_result", {}) or {})
            last_result.update({
                "diagnostic_id": str(
                    diagnostic.get("diagnostic_id", "")
                ),
                "diagnostic_category": str(
                    diagnostic.get("category", "UNKNOWN")
                ),
                "diagnostic_severity": str(
                    diagnostic.get("severity", "WARNING")
                ),
                "repairable": bool(
                    diagnostic.get("repairable", False)
                ),
                "requires_approval": bool(
                    diagnostic.get("requires_approval", False)
                ),
            })
            value["last_result"] = long_running_store.compact_result(
                last_result
            )
            root_cause = str(
                diagnostic.get("root_cause", "")
            ).strip()
            if root_cause:
                value["last_error"] = root_cause[:4000]

            if (
                str(diagnostic.get("category", "")).upper()
                == "APPROVAL_REQUIRED"
            ):
                value["state"] = "WAITING_APPROVAL"
                value["next_run_at"] = ""
                value["completed_at"] = ""
                waiting_approval += 1

            long_running_store.save_job(value)
            updated_job_ids.append(job_id)
        except Exception as error:  # migration must continue per job
            errors.append(
                f"{job_id}: {type(error).__name__}: {error}"
            )

    long_running_store.compact()
    return {
        "success": not errors,
        "status": "B54_DIAGNOSTICS_MIGRATION_COMPLETED",
        "scanned": scanned,
        "diagnosed": diagnosed,
        "waiting_approval": waiting_approval,
        "updated_job_ids": updated_job_ids,
        "errors": errors,
        "diagnostics_path": str(diagnostics.store.path),
        "long_running_path": str(long_running_store.path),
    }


def main() -> int:
    result = migrate(Path.cwd())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())

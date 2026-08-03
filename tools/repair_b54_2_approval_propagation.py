from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return dict(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    return dict(value) if isinstance(value, dict) else dict(default)


def _save_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(
                payload,
                stream,
                ensure_ascii=False,
                indent=2,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def repair(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve(strict=False)
    data_root = root / "data" / "autodev"
    queue_path = data_root / "long_running_autonomy.json"
    runs_path = data_root / "full_autonomy_runs.json"
    timestamp = _now()

    queue = _load(
        queue_path,
        {
            "version": 1,
            "updated_at": "",
            "jobs": {},
            "order": [],
            "events": [],
            "runtime": {},
            "policy": {},
        },
    )
    jobs = queue.get("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}
        queue["jobs"] = jobs

    runs = _load(
        runs_path,
        {
            "version": 1,
            "updated_at": "",
            "runs": {},
            "order": [],
        },
    )
    run_values = runs.get("runs", {})
    if not isinstance(run_values, dict):
        run_values = {}
        runs["runs"] = run_values

    rearmed: list[str] = []
    reset_run_ids: list[str] = []

    for job_id, raw_job in list(jobs.items()):
        if not isinstance(raw_job, dict):
            continue
        job = dict(raw_job)
        metadata = dict(job.get("metadata", {}) or {})
        repair_id = str(
            metadata.get("b54_last_repair_id", "")
        ).strip()
        consumed_id = str(
            metadata.get(
                "b54_repair_approval_consumed_id",
                "",
            )
        ).strip()

        eligible = (
            str(job.get("state", "")).upper()
            == "WAITING_APPROVAL"
            and str(
                metadata.get(
                    "b54_last_repair_type",
                    "",
                )
            ).upper()
            == "ONE_TIME_APPROVAL"
            and bool(
                metadata.get(
                    "b54_repair_approval_consumed",
                    False,
                )
            )
            and bool(repair_id)
            and consumed_id == repair_id
        )
        if not eligible:
            continue

        context = dict(
            job.get("execution_context", {}) or {}
        )
        context["auto_approve"] = False
        context["_b54_one_time_auto_approve"] = True
        context["_b54_repair_id"] = repair_id

        metadata.pop(
            "b54_repair_approval_consumed",
            None,
        )
        metadata.pop(
            "b54_repair_approval_consumed_id",
            None,
        )
        metadata.update({
            "b54_2_approval_rearmed_at": timestamp,
            "b54_2_approval_rearmed": True,
        })

        job.update({
            "state": "QUEUED",
            "attempts": 0,
            "next_run_at": timestamp,
            "completed_at": "",
            "last_error": "",
            "execution_context": context,
            "metadata": metadata,
            "updated_at": timestamp,
        })
        jobs[str(job_id)] = job
        rearmed.append(str(job_id))

        autonomy_run_id = str(
            job.get("autonomy_run_id", "")
        ).strip()
        run = run_values.get(autonomy_run_id)
        if isinstance(run, dict):
            run = dict(run)
            policy = dict(run.get("policy", {}) or {})
            policy["auto_approve"] = False
            run["policy"] = policy
            run_metadata = dict(
                run.get("metadata", {}) or {}
            )
            run_metadata.update({
                "b54_2_one_time_approval_rearmed": True,
                "b54_2_repair_id": repair_id,
            })
            run["metadata"] = run_metadata
            run_values[autonomy_run_id] = run
            reset_run_ids.append(autonomy_run_id)

    if rearmed:
        events = queue.get("events", [])
        if not isinstance(events, list):
            events = []
        for job_id in rearmed:
            events.append({
                "event": (
                    "LONG_RUNNING_ONE_TIME_APPROVAL_REARMED"
                ),
                "job_id": job_id,
                "timestamp": timestamp,
                "metadata": {
                    "source": "B54.2",
                },
            })
        queue["events"] = events[-500:]
        queue["updated_at"] = timestamp
        runtime = dict(queue.get("runtime", {}) or {})
        runtime["last_error"] = ""
        queue["runtime"] = runtime
        runs["updated_at"] = timestamp
        _save_atomic(queue_path, queue)
        _save_atomic(runs_path, runs)

    return {
        "success": True,
        "status": "B54_2_APPROVAL_PROPAGATION_REPAIRED",
        "rearmed": len(rearmed),
        "rearmed_job_ids": rearmed,
        "reset_run_policy_ids": reset_run_ids,
        "queue_path": str(queue_path),
        "runs_path": str(runs_path),
        "errors": [],
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    result = repair(project_root)
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

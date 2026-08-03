from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Iterable

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AutonomyControlCenterV2:
    """B105 durable single-execution queue with pause, resume and cancel."""

    ACTIVE = {"RUNNING", "PAUSED"}
    TERMINAL = {"COMPLETED", "CANCELLED", "FAILED"}

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "intelligence" / "autonomy2.json",
            self._default,
        )
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "2.0",
            "jobs": {},
            "queue": [],
            "active_job_id": "",
            "lease": {},
            "events": [],
            "updated_at": "",
        }

    def create_job(
        self,
        title: object,
        steps: Iterable[object],
        *,
        priority: int = 50,
    ) -> dict[str, Any]:
        name = " ".join(str(title).split()).strip()
        clean_steps = [" ".join(str(step).split()).strip() for step in steps if str(step).strip()]
        if not name or not clean_steps:
            raise ValueError("Zadanie wymaga nazwy i co najmniej jednego kroku.")
        now = utc_now()
        job_id = "job-" + hashlib.sha256(f"{name}|{now}".encode("utf-8")).hexdigest()[:12]
        job = {
            "job_id": job_id,
            "title": name[:200],
            "steps": [
                {"index": index, "title": step[:500], "status": "PENDING", "result": ""}
                for index, step in enumerate(clean_steps)
            ],
            "current_step": 0,
            "status": "QUEUED",
            "priority": max(0, min(int(priority), 100)),
            "created_at": now,
            "updated_at": now,
        }
        data = self._load()
        jobs = dict(data.get("jobs", {}) or {})
        jobs[job_id] = job
        queue = list(data.get("queue", []) or [])
        queue.append(job_id)
        queue.sort(key=lambda key: jobs[key].get("priority", 0), reverse=True)
        data["jobs"] = jobs
        data["queue"] = queue
        self._event(data, job_id, "CREATED")
        self.store.save(data)
        return job

    def start(self, job_id: str = "") -> dict[str, Any]:
        data = self._load()
        active_id = str(data.get("active_job_id", ""))
        if active_id and dict(data.get("jobs", {})).get(active_id, {}).get("status") in self.ACTIVE:
            raise RuntimeError("B105 zachowuje maksymalnie jedno aktywne wykonanie.")
        queue = list(data.get("queue", []) or [])
        selected = str(job_id or (queue[0] if queue else ""))
        jobs = dict(data.get("jobs", {}) or {})
        job = dict(jobs.get(selected, {}) or {})
        if not job:
            raise KeyError("Brak zadania gotowego do uruchomienia.")
        if job.get("status") in self.TERMINAL:
            raise ValueError("Nie można uruchomić zakończonego zadania.")
        job["status"] = "RUNNING"
        job["updated_at"] = utc_now()
        steps = list(job.get("steps", []) or [])
        current = int(job.get("current_step", 0) or 0)
        if current < len(steps) and steps[current].get("status") == "PENDING":
            steps[current]["status"] = "RUNNING"
        job["steps"] = steps
        jobs[selected] = job
        data["jobs"] = jobs
        data["queue"] = [item for item in queue if item != selected]
        data["active_job_id"] = selected
        data["lease"] = {
            "job_id": selected,
            "lease_id": hashlib.sha256(f"{selected}|{utc_now()}".encode("utf-8")).hexdigest()[:20],
            "acquired_at": utc_now(),
            "heartbeat_at": utc_now(),
        }
        self._event(data, selected, "STARTED")
        self.store.save(data)
        return job

    def advance(self, result: object = "OK") -> dict[str, Any]:
        data = self._load()
        job = self._active(data)
        if job.get("status") != "RUNNING":
            raise RuntimeError("Aktywne zadanie nie jest uruchomione.")
        steps = list(job.get("steps", []) or [])
        current = int(job.get("current_step", 0) or 0)
        if current >= len(steps):
            return self._complete(data, job)
        steps[current]["status"] = "COMPLETED"
        steps[current]["result"] = str(result)[:1000]
        current += 1
        job["current_step"] = current
        if current >= len(steps):
            job["steps"] = steps
            return self._complete(data, job)
        steps[current]["status"] = "RUNNING"
        job["steps"] = steps
        job["updated_at"] = utc_now()
        self._save_active(data, job, "STEP_COMPLETED")
        return job

    def pause(self) -> dict[str, Any]:
        return self._set_active("PAUSED", "PAUSED")

    def resume(self) -> dict[str, Any]:
        return self._set_active("RUNNING", "RESUMED")

    def cancel(self) -> dict[str, Any]:
        data = self._load()
        job = self._active(data)
        job["status"] = "CANCELLED"
        job["updated_at"] = utc_now()
        jobs = dict(data.get("jobs", {}) or {})
        jobs[job["job_id"]] = job
        data["jobs"] = jobs
        data["active_job_id"] = ""
        data["lease"] = {}
        self._event(data, job["job_id"], "CANCELLED")
        self.store.save(data)
        return job

    def status(self) -> dict[str, Any]:
        data = self._load()
        jobs = dict(data.get("jobs", {}) or {})
        active_id = str(data.get("active_job_id", ""))
        active = dict(jobs.get(active_id, {}) or {})
        steps = list(active.get("steps", []) or [])
        completed = sum(item.get("status") == "COMPLETED" for item in steps)
        current = int(active.get("current_step", 0) or 0)
        return {
            "status": "AUTONOMY_CONTROL_CENTER_2_READY",
            "job_count": len(jobs),
            "queued_count": len(list(data.get("queue", []) or [])),
            "active_job": {
                "job_id": active.get("job_id", ""),
                "title": active.get("title", ""),
                "status": active.get("status", "IDLE"),
                "completed_steps": completed,
                "total_steps": len(steps),
                "progress_percent": round((completed / len(steps)) * 100, 1) if steps else 0.0,
                "next_step": steps[current].get("title", "") if current < len(steps) else "",
            },
            "lease": dict(data.get("lease", {}) or {}),
            "event_count": len(list(data.get("events", []) or [])),
            "safety": {"auto_approve": False, "max_active_executions": 1},
        }

    def _set_active(self, status: str, event: str) -> dict[str, Any]:
        data = self._load()
        job = self._active(data)
        if status == "PAUSED" and job.get("status") != "RUNNING":
            raise RuntimeError("Można wstrzymać tylko uruchomione zadanie.")
        if status == "RUNNING" and job.get("status") != "PAUSED":
            raise RuntimeError("Można wznowić tylko wstrzymane zadanie.")
        job["status"] = status
        job["updated_at"] = utc_now()
        self._save_active(data, job, event)
        return job

    def _complete(self, data: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
        job["status"] = "COMPLETED"
        job["updated_at"] = utc_now()
        jobs = dict(data.get("jobs", {}) or {})
        jobs[job["job_id"]] = job
        data["jobs"] = jobs
        data["active_job_id"] = ""
        data["lease"] = {}
        self._event(data, job["job_id"], "COMPLETED")
        self.store.save(data)
        return job

    def _save_active(self, data: dict[str, Any], job: dict[str, Any], event: str) -> None:
        jobs = dict(data.get("jobs", {}) or {})
        jobs[job["job_id"]] = job
        data["jobs"] = jobs
        lease = dict(data.get("lease", {}) or {})
        if lease:
            lease["heartbeat_at"] = utc_now()
            data["lease"] = lease
        self._event(data, job["job_id"], event)
        self.store.save(data)

    @staticmethod
    def _active(data: dict[str, Any]) -> dict[str, Any]:
        active_id = str(data.get("active_job_id", ""))
        job = dict(dict(data.get("jobs", {}) or {}).get(active_id, {}) or {})
        if not job:
            raise KeyError("Brak aktywnego zadania B105.")
        return job

    @staticmethod
    def _event(data: dict[str, Any], job_id: str, event: str) -> None:
        events = list(data.get("events", []) or [])
        events.append({"job_id": job_id, "event": event, "created_at": utc_now()})
        data["events"] = events[-1000:]
        data["updated_at"] = utc_now()

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

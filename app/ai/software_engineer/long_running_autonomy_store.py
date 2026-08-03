from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .long_running_autonomy_models import LongRunningJob


class LongRunningAutonomyStore:
    """Atomic bounded state for scheduled autonomous operations."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_jobs: int = 200,
        max_events: int = 1000,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.max_jobs = min(1000, max(20, int(max_jobs)))
        self.max_events = min(5000, max(100, int(max_events)))
        self.path = (
            self.paths.autodev_data
            / "long_running_autonomy.json"
        )
        self._store = JsonStore(
            self.path,
            self._default_payload,
        )

    def load(self) -> dict[str, Any]:
        return self._payload(self._store.load())

    def save_job(
        self,
        job: LongRunningJob | dict[str, Any],
    ) -> dict[str, Any]:
        value = (
            job.to_dict()
            if isinstance(job, LongRunningJob)
            else LongRunningJob.from_dict(dict(job)).to_dict()
        )
        value["last_result"] = self.compact_result(
            value.get("last_result")
        )
        job_id = str(value.get("job_id", "")).strip()
        if not job_id:
            raise ValueError("Zadanie długotrwałe wymaga job_id.")

        payload = self.load()
        value["updated_at"] = self._now()
        payload["jobs"][job_id] = value
        order = payload["order"]
        if job_id in order:
            order.remove(job_id)
        order.append(job_id)

        while len(order) > self.max_jobs:
            removed = order.pop(0)
            payload["jobs"].pop(removed, None)

        payload["updated_at"] = value["updated_at"]
        self._store.save(payload)
        return dict(value)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        value = self.load()["jobs"].get(str(job_id).strip())
        return dict(value) if isinstance(value, dict) else None

    def delete_job(self, job_id: str) -> dict[str, Any] | None:
        key = str(job_id).strip()
        if not key:
            return None
        payload = self.load()
        removed = payload["jobs"].pop(key, None)
        if not isinstance(removed, dict):
            return None
        payload["order"] = [
            item for item in payload["order"] if item != key
        ]
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(removed)

    def delete_jobs_by_state(
        self,
        states: set[str],
    ) -> list[dict[str, Any]]:
        allowed = {str(item).upper() for item in states}
        payload = self.load()
        removed: list[dict[str, Any]] = []
        kept_order: list[str] = []
        for job_id in payload["order"]:
            job = payload["jobs"].get(job_id)
            if (
                isinstance(job, dict)
                and str(job.get("state", "")).upper() in allowed
            ):
                removed.append(dict(job))
                payload["jobs"].pop(job_id, None)
            else:
                kept_order.append(job_id)
        payload["order"] = kept_order
        if removed:
            payload["updated_at"] = self._now()
            self._store.save(payload)
        return removed

    def list_jobs(
        self,
        *,
        limit: int = 50,
        states: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.load()
        selected = payload["order"][
            -min(self.max_jobs, max(1, int(limit))):
        ]
        allowed = {
            str(item).upper()
            for item in (states or set())
        }
        result: list[dict[str, Any]] = []
        for job_id in reversed(selected):
            job = payload["jobs"].get(job_id)
            if not isinstance(job, dict):
                continue
            if allowed and str(job.get("state", "")).upper() not in allowed:
                continue
            result.append(dict(job))
        return result

    def runtime(self) -> dict[str, Any]:
        return dict(self.load()["runtime"])

    def update_runtime(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.load()
        safe_updates = dict(updates)
        if "last_result" in safe_updates:
            safe_updates["last_result"] = self.compact_result(
                safe_updates.get("last_result")
            )
        runtime = {
            **payload["runtime"],
            **safe_updates,
        }
        runtime["updated_at"] = self._now()
        payload["runtime"] = runtime
        payload["updated_at"] = runtime["updated_at"]
        self._store.save(payload)
        return dict(runtime)

    def policy(self) -> dict[str, Any]:
        return dict(self.load()["policy"])

    def update_policy(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.load()
        policy = {
            **payload["policy"],
            **dict(updates),
        }
        payload["policy"] = self._normalize_policy(policy)
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(payload["policy"])

    def record_event(
        self,
        event: str,
        *,
        job_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self.load()
        value = {
            "event": str(event),
            "job_id": str(job_id),
            "created_at": self._now(),
            "metadata": dict(metadata or {}),
        }
        payload["events"].append(value)
        payload["events"] = payload["events"][-self.max_events:]
        payload["updated_at"] = value["created_at"]
        self._store.save(payload)
        return value

    def compact(self) -> dict[str, Any]:
        """Persist a bounded, normalized copy of runtime state."""
        payload = self.load()
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return {
            "jobs": len(payload["jobs"]),
            "events": len(payload["events"]),
            "path": str(self.path),
        }

    @classmethod
    def compact_result(
        cls,
        value: Any,
    ) -> dict[str, Any]:
        """Keep only bounded monitoring fields from large responses."""
        if not isinstance(value, dict):
            return {}

        source = dict(value)
        autonomy_run = (
            dict(source.get("autonomy_run", {}))
            if isinstance(source.get("autonomy_run"), dict)
            else {}
        )
        execution = (
            dict(source.get("execution", {}))
            if isinstance(source.get("execution"), dict)
            else {}
        )

        result: dict[str, Any] = {}
        scalar_keys = (
            "success",
            "status",
            "operation",
            "job_id",
            "autonomy_run_id",
            "goal_id",
            "portfolio_id",
            "director_run_id",
            "progress_percent",
            "changed_files_count",
            "campaigns_total",
            "campaigns_completed",
            "campaigns_failed",
            "stages_total",
            "stages_completed",
            "current_campaign_id",
            "current_stage_id",
            "allowed",
            "recovered",
            "removed",
            "report_path",
            "diagnostic_id",
            "diagnostic_category",
            "diagnostic_severity",
            "repairable",
            "requires_approval",
            "phase",
            "updated_at",
            "approval_lease_state",
            "approval_lease_id",
        )

        for key in scalar_keys:
            selected = source.get(key)
            if selected is None and key in autonomy_run:
                selected = autonomy_run.get(key)
            if selected is None and key in execution:
                selected = execution.get(key)
            if selected is None:
                continue
            if isinstance(selected, str):
                result[key] = selected[:2000]
            elif isinstance(selected, (bool, int, float)):
                result[key] = selected

        for key in ("errors", "reasons"):
            items = source.get(key, [])
            if isinstance(items, list):
                result[key] = [
                    str(item)[:1000]
                    for item in items[:10]
                ]

        sample = source.get("sample")
        if isinstance(sample, dict):
            result["sample"] = {
                str(key)[:100]: item
                for key, item in list(sample.items())[:20]
                if isinstance(item, (str, bool, int, float))
            }

        jobs = source.get("jobs")
        if isinstance(jobs, list):
            result["processed_jobs"] = [
                {
                    "job_id": str(item.get("job_id", ""))[:200],
                    "state": str(item.get("state", ""))[:100],
                    "attempts": int(item.get("attempts", 0) or 0),
                    "max_attempts": int(
                        item.get("max_attempts", 0) or 0
                    ),
                }
                for item in jobs[:20]
                if isinstance(item, dict)
            ]

        return result

    def events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        values = self.load()["events"][
            -max(1, min(self.max_events, int(limit))):
        ]
        return [
            dict(item)
            for item in reversed(values)
            if isinstance(item, dict)
        ]

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": "",
            "jobs": {},
            "order": [],
            "events": [],
            "runtime": {
                "enabled": False,
                "paused": False,
                "running": False,
                "heartbeat_at": "",
                "last_tick_at": "",
                "last_result": {},
                "last_error": "",
                "cycles_completed": 0,
                "recovered_jobs": 0,
                "updated_at": "",
            },
            "policy": LongRunningAutonomyStore._normalize_policy({}),
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        payload = dict(value) if isinstance(value, dict) else {}
        defaults = cls._default_payload()
        jobs = payload.get("jobs", {})
        order = payload.get("order", [])
        events = payload.get("events", [])

        normalized_jobs: dict[str, dict[str, Any]] = {}
        if isinstance(jobs, dict):
            for key, item in jobs.items():
                if not isinstance(item, dict):
                    continue
                normalized = LongRunningJob.from_dict(item).to_dict()
                normalized["last_result"] = cls.compact_result(
                    normalized.get("last_result")
                )
                normalized_jobs[str(key)] = normalized

        normalized_order = [
            str(job_id)
            for job_id in order
            if str(job_id) in normalized_jobs
        ] if isinstance(order, list) else []
        for job_id in normalized_jobs:
            if job_id not in normalized_order:
                normalized_order.append(job_id)

        runtime = {
            **defaults["runtime"],
            **(
                dict(payload.get("runtime", {}))
                if isinstance(payload.get("runtime"), dict)
                else {}
            ),
        }
        runtime["last_result"] = cls.compact_result(
            runtime.get("last_result")
        )

        return {
            "version": 1,
            "updated_at": str(payload.get("updated_at", "")),
            "jobs": normalized_jobs,
            "order": normalized_order,
            "events": [
                dict(item)
                for item in events
                if isinstance(item, dict)
            ][-5000:],
            "runtime": runtime,
            "policy": cls._normalize_policy(
                payload.get("policy", {})
                if isinstance(payload.get("policy"), dict)
                else {}
            ),
        }

    @staticmethod
    def _normalize_policy(value: dict[str, Any]) -> dict[str, Any]:
        def number(
            key: str,
            default: float,
            minimum: float,
            maximum: float,
        ) -> float:
            try:
                parsed = float(value.get(key, default))
            except (TypeError, ValueError):
                parsed = default
            return min(maximum, max(minimum, parsed))

        return {
            "interval_seconds": number(
                "interval_seconds", 15.0, 1.0, 3600.0
            ),
            "max_parallel_jobs": int(number(
                "max_parallel_jobs", 1, 1, 3
            )),
            "max_jobs_per_tick": int(number(
                "max_jobs_per_tick", 1, 1, 10
            )),
            "max_cpu_percent": number(
                "max_cpu_percent", 85.0, 20.0, 98.0
            ),
            "max_memory_percent": number(
                "max_memory_percent", 90.0, 20.0, 98.0
            ),
            "min_disk_free_gb": number(
                "min_disk_free_gb", 2.0, 0.5, 100.0
            ),
            "resource_retry_seconds": number(
                "resource_retry_seconds", 60.0, 5.0, 3600.0
            ),
            "failure_retry_seconds": number(
                "failure_retry_seconds", 120.0, 5.0, 7200.0
            ),
            "stale_after_seconds": number(
                "stale_after_seconds", 300.0, 30.0, 86400.0
            ),
            "require_ac_power": bool(
                value.get("require_ac_power", False)
            ),
            "auto_rollback": bool(
                value.get("auto_rollback", True)
            ),
            "final_validation": bool(
                value.get("final_validation", True)
            ),
            "auto_approve": False,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

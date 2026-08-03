from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .self_directed_development_models import (
    SelfDirectedDevelopmentPolicy,
)


class SelfDirectedDevelopmentStore:
    """Atomic and bounded state for the B56 autonomous development loop."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_history: int = 500,
        max_observed_jobs: int = 2000,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = (
            self.paths.autodev_data
            / "self_directed_development.json"
        )
        self.max_history = min(5000, max(50, int(max_history)))
        self.max_observed_jobs = min(
            10000,
            max(100, int(max_observed_jobs)),
        )
        self._store = JsonStore(self.path, self._default_payload)

    def load(self) -> dict[str, Any]:
        return self._payload(self._store.load())

    def runtime(self) -> dict[str, Any]:
        return dict(self.load()["runtime"])

    def update_runtime(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.load()
        runtime = {
            **payload["runtime"],
            **dict(updates),
            "updated_at": self._now(),
        }
        payload["runtime"] = self._compact_runtime(runtime)
        payload["updated_at"] = runtime["updated_at"]
        self._store.save(payload)
        return dict(payload["runtime"])

    def policy(self) -> dict[str, Any]:
        return dict(self.load()["policy"])

    def update_policy(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.load()
        policy = SelfDirectedDevelopmentPolicy.from_dict({
            **payload["policy"],
            **dict(updates),
            "auto_approve": False,
        }).to_dict()
        payload["policy"] = policy
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(policy)

    def record_history(
        self,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.load()
        item = self._compact_history(dict(value))
        item["created_at"] = str(
            item.get("created_at", "") or self._now()
        )
        payload["history"].append(item)
        payload["history"] = payload["history"][-self.max_history:]
        payload["updated_at"] = item["created_at"]
        self._store.save(payload)
        return dict(item)

    def history(self, *, limit: int = 20) -> list[dict[str, Any]]:
        values = self.load()["history"][-max(1, int(limit)):]
        return [
            dict(item)
            for item in reversed(values)
            if isinstance(item, dict)
        ]

    def has_observed(self, job_id: str) -> bool:
        key = str(job_id).strip()
        return bool(key and key in self.load()["observed_jobs"])

    def mark_observed(self, job_id: str) -> None:
        key = str(job_id).strip()
        if not key:
            return
        payload = self.load()
        observed = payload["observed_jobs"]
        if key in observed:
            observed.remove(key)
        observed.append(key)
        payload["observed_jobs"] = observed[-self.max_observed_jobs:]
        payload["updated_at"] = self._now()
        self._store.save(payload)

    def compact(self) -> dict[str, Any]:
        payload = self.load()
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return {
            "history": len(payload["history"]),
            "observed_jobs": len(payload["observed_jobs"]),
            "path": str(self.path),
        }

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": "",
            "runtime": {
                "enabled": False,
                "paused": False,
                "running": False,
                "phase": "IDLE",
                "cycles_completed": 0,
                "last_cycle_at": "",
                "last_scan_at": "",
                "last_dispatch_at": "",
                "last_dispatch_job_id": "",
                "active_job_id": "",
                "waiting_approval_job_id": "",
                "consecutive_failures": 0,
                "cooldown_until": "",
                "dispatch_day": "",
                "dispatches_today": 0,
                "completed_total": 0,
                "failed_total": 0,
                "deferred_total": 0,
                "last_outcome": {},
                "last_result": {},
                "last_error": "",
                "updated_at": "",
            },
            "policy": SelfDirectedDevelopmentPolicy().to_dict(),
            "history": [],
            "observed_jobs": [],
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        runtime = source.get("runtime", {})
        history = source.get("history", [])
        observed = source.get("observed_jobs", [])
        return {
            "version": 1,
            "updated_at": str(source.get("updated_at", "")),
            "runtime": cls._compact_runtime({
                **cls._default_payload()["runtime"],
                **(dict(runtime) if isinstance(runtime, dict) else {}),
            }),
            "policy": SelfDirectedDevelopmentPolicy.from_dict(
                source.get("policy")
                if isinstance(source.get("policy"), dict)
                else {}
            ).to_dict(),
            "history": [
                cls._compact_history(dict(item))
                for item in history[-5000:]
                if isinstance(item, dict)
            ] if isinstance(history, list) else [],
            "observed_jobs": [
                str(item)[:200]
                for item in observed[-10000:]
                if str(item).strip()
            ] if isinstance(observed, list) else [],
        }

    @staticmethod
    def _compact_runtime(value: dict[str, Any]) -> dict[str, Any]:
        result = dict(value)
        for key, limit in (
            ("phase", 100),
            ("last_dispatch_job_id", 200),
            ("active_job_id", 200),
            ("waiting_approval_job_id", 200),
            ("last_error", 4000),
        ):
            result[key] = str(result.get(key, ""))[:limit]
        result["cycles_completed"] = max(
            0,
            int(result.get("cycles_completed", 0) or 0),
        )
        for key in (
            "consecutive_failures",
            "dispatches_today",
            "completed_total",
            "failed_total",
            "deferred_total",
        ):
            result[key] = max(0, int(result.get(key, 0) or 0))
        for key in ("last_outcome", "last_result"):
            item = result.get(key, {})
            result[key] = (
                SelfDirectedDevelopmentStore._compact_mapping(item)
                if isinstance(item, dict)
                else {}
            )
        return result

    @staticmethod
    def _compact_history(value: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "status",
            "success",
            "phase",
            "job_id",
            "opportunity_id",
            "outcome",
            "scan_status",
            "dispatch_status",
            "reason",
            "error",
            "created_at",
        )
        return {
            key: (
                str(value.get(key, ""))[:4000]
                if key not in {"success"}
                else bool(value.get(key, False))
            )
            for key in allowed
            if key in value
        }

    @staticmethod
    def _compact_mapping(value: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:80]:
            name = str(key)[:100]
            if isinstance(item, str):
                result[name] = item[:4000]
            elif isinstance(item, (bool, int, float)) or item is None:
                result[name] = item
            else:
                result[name] = str(item)[:4000]
        return result

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

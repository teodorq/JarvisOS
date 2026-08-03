from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .autonomy_governance_models import (
    default_stage_policies,
    harden_stage_policy,
)


_STAGE_SECTIONS = {
    "B62": "deployments",
    "B63": "goal_actions",
    "B64": "leases",
    "B65": "hypotheses",
    "B66": "releases",
    "B67": "findings",
    "B68": "cycles",
    "B69": "incidents",
    "B70": "recovery_plans",
    "B71": "recovery_executions",
    "B72": "recovery_lessons",
    "B73": "control_snapshots",
    "B74": "watchdog_events",
    "B75": "safe_deployments",
    "B76": "release_trains",
    "B77": "development_memories",
    "B78": "security_findings",
    "B79": "production_cycles",
}


class AutonomyGovernanceStore:
    """Atomic shared state for the integrated B62-B79 autonomy suite."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_history: int = 5000,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.autodev_data / "autonomy_governance_b62_b68.json"
        self.max_history = min(20000, max(500, int(max_history)))
        self._store = JsonStore(self.path, self._default_payload)
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            return self._payload(self._store.load())

    def save(self, payload: dict[str, Any]) -> None:
        with self._lock:
            value = self._payload(payload)
            value["updated_at"] = self._now()
            self._store.save(value)

    def runtime(self, stage: str) -> dict[str, Any]:
        key = self._stage(stage)
        return dict(self.load()["runtime"][key])

    def update_runtime(
        self,
        stage: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        key = self._stage(stage)
        with self._lock:
            payload = self.load()
            value = {
                **payload["runtime"][key],
                **dict(updates),
                "updated_at": self._now(),
            }
            payload["runtime"][key] = self._compact_runtime(value)
            self.save(payload)
            return dict(payload["runtime"][key])

    def policy(self, stage: str) -> dict[str, Any]:
        key = self._stage(stage)
        return dict(self.load()["policy"][key])

    def update_policy(
        self,
        stage: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        key = self._stage(stage)
        with self._lock:
            payload = self.load()
            policy = harden_stage_policy(
                key,
                {**payload["policy"][key], **dict(updates)},
            )
            payload["policy"][key] = policy
            self.save(payload)
            return dict(policy)

    def append_record(
        self,
        stage: str,
        value: dict[str, Any],
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        key = self._stage(stage)
        section = _STAGE_SECTIONS[key]
        with self._lock:
            payload = self.load()
            item = self._compact_record(key, dict(value))
            payload[section].append(item)
            maximum = int(limit or self._section_limit(key, payload))
            payload[section] = payload[section][-max(1, maximum):]
            self.save(payload)
            return dict(item)

    def list_records(
        self,
        stage: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        key = self._stage(stage)
        section = _STAGE_SECTIONS[key]
        values = self.load()[section][-max(1, int(limit)):]
        return [dict(item) for item in reversed(values) if isinstance(item, dict)]

    def replace_records(
        self,
        stage: str,
        values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        key = self._stage(stage)
        section = _STAGE_SECTIONS[key]
        with self._lock:
            payload = self.load()
            maximum = self._section_limit(key, payload)
            payload[section] = [
                self._compact_record(key, dict(item))
                for item in values[-maximum:]
                if isinstance(item, dict)
            ]
            self.save(payload)
            return self.list_records(key, limit=maximum)

    def record_history(
        self,
        stage: str,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        key = self._stage(stage)
        with self._lock:
            payload = self.load()
            item = {
                "stage": key,
                "status": str(value.get("status", "UNKNOWN"))[:120],
                "success": bool(value.get("success", False)),
                "phase": str(value.get("phase", ""))[:100],
                "decision": str(value.get("decision", ""))[:100],
                "reason": str(value.get("reason", ""))[-3000:],
                "error": str(value.get("error", ""))[-3000:],
                "metadata": dict(value.get("metadata", {}) or {}),
                "created_at": str(value.get("created_at") or self._now()),
            }
            payload["history"].append(item)
            payload["history"] = payload["history"][-self.max_history:]
            self.save(payload)
            return dict(item)

    def history(
        self,
        *,
        stage: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        key = str(stage).upper().strip()
        result: list[dict[str, Any]] = []
        for item in reversed(self.load()["history"]):
            if not isinstance(item, dict):
                continue
            if key and str(item.get("stage", "")).upper() != key:
                continue
            result.append(dict(item))
            if len(result) >= max(1, int(limit)):
                break
        return result

    def summary(self, stage: str) -> dict[str, Any]:
        key = self._stage(stage)
        records = self.list_records(key, limit=10000)
        statuses: dict[str, int] = {}
        for item in records:
            status = str(item.get("status", "UNKNOWN")).upper()
            statuses[status] = statuses.get(status, 0) + 1
        runtime = self.runtime(key)
        return {
            "stage": key,
            "records": len(records),
            "counts": statuses,
            "cycles_completed": int(runtime.get("cycles_completed", 0) or 0),
            "phase": str(runtime.get("phase", "IDLE")),
            "enabled": bool(runtime.get("enabled", False)),
            "running": bool(runtime.get("running", False)),
            "paused": bool(runtime.get("paused", False)),
            "path": str(self.path),
        }

    def compact(self) -> dict[str, Any]:
        payload = self.load()
        self.save(payload)
        return {
            stage: self.summary(stage)
            for stage in sorted(_STAGE_SECTIONS)
        }

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        policies = default_stage_policies()
        return {
            "version": 1,
            "updated_at": "",
            "runtime": {
                stage: AutonomyGovernanceStore._default_runtime(stage)
                for stage in policies
            },
            "policy": policies,
            "deployments": [],
            "goal_actions": [],
            "leases": [],
            "hypotheses": [],
            "releases": [],
            "findings": [],
            "cycles": [],
            "incidents": [],
            "recovery_plans": [],
            "recovery_executions": [],
            "recovery_lessons": [],
            "control_snapshots": [],
            "watchdog_events": [],
            "safe_deployments": [],
            "release_trains": [],
            "development_memories": [],
            "security_findings": [],
            "production_cycles": [],
            "history": [],
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        defaults = cls._default_payload()
        runtime_source = source.get("runtime", {})
        runtime_source = runtime_source if isinstance(runtime_source, dict) else {}
        policy_source = source.get("policy", {})
        policy_source = policy_source if isinstance(policy_source, dict) else {}
        payload = {
            "version": 1,
            "updated_at": str(source.get("updated_at", ""))[:100],
            "runtime": {},
            "policy": {},
            "history": [
                dict(item)
                for item in source.get("history", [])[-20000:]
                if isinstance(item, dict)
            ] if isinstance(source.get("history"), list) else [],
        }
        for stage in sorted(_STAGE_SECTIONS):
            payload["runtime"][stage] = cls._compact_runtime({
                **defaults["runtime"][stage],
                **dict(runtime_source.get(stage, {}) or {}),
            })
            payload["policy"][stage] = harden_stage_policy(
                stage,
                dict(policy_source.get(stage, {}) or {}),
            )
            section = _STAGE_SECTIONS[stage]
            values = source.get(section, [])
            values = values if isinstance(values, list) else []
            limit = cls._static_section_limit(stage, payload["policy"][stage])
            payload[section] = [
                cls._compact_record(stage, dict(item))
                for item in values[-limit:]
                if isinstance(item, dict)
            ]
        return payload

    @staticmethod
    def _default_runtime(stage: str) -> dict[str, Any]:
        enabled = stage not in {
            "B68", "B69", "B70", "B72", "B74", "B79",
        }
        return {
            "enabled": enabled,
            "paused": False,
            "running": False,
            "phase": "IDLE",
            "cycles_completed": 0,
            "consecutive_failures": 0,
            "last_cycle_at": "",
            "last_status": "",
            "last_decision": "",
            "last_record_id": "",
            "last_result": {},
            "last_error": "",
            "budget_date": "",
            "cycles_used_today": 0,
            "active_leases": 0,
            "updated_at": "",
        }

    @staticmethod
    def _compact_runtime(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "enabled": bool(value.get("enabled", False)),
            "paused": bool(value.get("paused", False)),
            "running": bool(value.get("running", False)),
            "phase": str(value.get("phase", "IDLE"))[:100],
            "cycles_completed": max(0, int(value.get("cycles_completed", 0) or 0)),
            "consecutive_failures": max(
                0, int(value.get("consecutive_failures", 0) or 0)
            ),
            "last_cycle_at": str(value.get("last_cycle_at", ""))[:100],
            "last_status": str(value.get("last_status", ""))[:150],
            "last_decision": str(value.get("last_decision", ""))[:100],
            "last_record_id": str(value.get("last_record_id", ""))[:250],
            "last_result": dict(value.get("last_result", {}) or {}),
            "last_error": str(value.get("last_error", ""))[-4000:],
            "budget_date": str(value.get("budget_date", ""))[:20],
            "cycles_used_today": max(0, int(value.get("cycles_used_today", 0) or 0)),
            "active_leases": max(0, int(value.get("active_leases", 0) or 0)),
            "updated_at": str(value.get("updated_at", ""))[:100],
        }

    @staticmethod
    def _compact_record(stage: str, value: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)[:100]
            if isinstance(item, dict):
                result[name] = deepcopy(item)
            elif isinstance(item, list):
                result[name] = deepcopy(item[:5000])
            elif isinstance(item, str):
                result[name] = item[-12000:]
            elif isinstance(item, (bool, int, float)) or item is None:
                result[name] = item
            else:
                result[name] = str(item)[-4000:]
        result["stage"] = stage
        result["status"] = str(result.get("status", "UNKNOWN")).upper()[:120]
        result["created_at"] = str(result.get("created_at") or AutonomyGovernanceStore._now())[:100]
        return result

    def _section_limit(self, stage: str, payload: dict[str, Any]) -> int:
        return self._static_section_limit(stage, payload["policy"][stage])

    @staticmethod
    def _static_section_limit(stage: str, policy: dict[str, Any]) -> int:
        if stage == "B65":
            return int(policy.get("max_hypotheses", 200))
        if stage == "B66":
            return int(policy.get("max_candidates", 50))
        if stage == "B67":
            return int(policy.get("max_findings", 500))
        if stage == "B69":
            return int(policy.get("max_incidents", 1000))
        limits = {
            "B70": ("max_plans", 1000),
            "B71": ("max_executions", 1000),
            "B72": ("max_lessons", 1000),
            "B73": ("max_snapshots", 1000),
            "B74": ("max_events", 1000),
            "B75": ("max_deployments", 500),
            "B76": ("max_release_trains", 500),
            "B77": ("max_memories", 5000),
            "B78": ("max_findings", 500),
            "B79": ("max_cycles", 5000),
        }
        if stage in limits:
            name, default = limits[stage]
            return int(policy.get(name, default))
        return 2000

    @staticmethod
    def _stage(stage: str) -> str:
        key = str(stage).upper().strip()
        if key not in _STAGE_SECTIONS:
            raise ValueError(f"Nieznany etap autonomii: {stage}")
        return key

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

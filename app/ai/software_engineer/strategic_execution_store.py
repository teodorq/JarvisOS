from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .strategic_execution_models import (
    ACTIVE_STRATEGIC_EXECUTION_STATES,
    StrategicExecutionPolicy,
    StrategicExecutionRecord,
)


class StrategicExecutionStore:
    """Atomic B58 goal -> opportunity -> long-running job bindings."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_records: int = 2000,
        max_history: int = 1000,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.autodev_data / "strategic_execution.json"
        self.max_records = min(10000, max(100, int(max_records)))
        self.max_history = min(5000, max(100, int(max_history)))
        self._store = JsonStore(self.path, self._default_payload)

    def load(self) -> dict[str, Any]:
        return self._payload(self._store.load())

    def save_record(
        self,
        record: StrategicExecutionRecord | dict[str, Any],
    ) -> dict[str, Any]:
        item = (
            record
            if isinstance(record, StrategicExecutionRecord)
            else StrategicExecutionRecord.from_dict(dict(record))
        )
        value = self._compact_record(item.to_dict())
        execution_id = str(value.get("execution_id", "")).strip()
        if not execution_id:
            raise ValueError("Wykonanie strategiczne wymaga execution_id.")
        payload = self.load()
        existing = payload["records"].get(execution_id, {})
        if str(existing.get("created_at", "")).strip():
            value["created_at"] = str(existing["created_at"])
        value["updated_at"] = self._now()
        payload["records"][execution_id] = value
        order = payload["order"]
        if execution_id in order:
            order.remove(execution_id)
        order.append(execution_id)
        limit = min(
            self.max_records,
            int(payload["policy"].get("max_records", self.max_records)),
        )
        while len(order) > limit:
            removable = next(
                (
                    record_id
                    for record_id in order
                    if str(
                        payload["records"].get(record_id, {}).get(
                            "status", ""
                        )
                    ).upper()
                    not in ACTIVE_STRATEGIC_EXECUTION_STATES
                ),
                order[0],
            )
            order.remove(removable)
            payload["records"].pop(removable, None)
        payload["updated_at"] = value["updated_at"]
        self._store.save(payload)
        return dict(value)

    def get_record(self, execution_id: str) -> dict[str, Any] | None:
        value = self.load()["records"].get(str(execution_id).strip())
        return dict(value) if isinstance(value, dict) else None

    def find_by_job(self, job_id: str) -> dict[str, Any] | None:
        key = str(job_id).strip()
        if not key:
            return None
        for item in self.list_records(limit=self.max_records):
            if str(item.get("job_id", "")).strip() == key:
                return item
        return None

    def find_by_opportunity(
        self,
        opportunity_id: str,
    ) -> dict[str, Any] | None:
        key = str(opportunity_id).strip()
        if not key:
            return None
        for item in self.list_records(limit=self.max_records):
            if str(item.get("opportunity_id", "")).strip() == key:
                return item
        return None

    def list_records(
        self,
        *,
        limit: int = 100,
        statuses: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.load()
        allowed = {str(item).upper() for item in (statuses or set())}
        result: list[dict[str, Any]] = []
        for execution_id in reversed(payload["order"]):
            item = payload["records"].get(execution_id)
            if not isinstance(item, dict):
                continue
            if allowed and str(item.get("status", "")).upper() not in allowed:
                continue
            result.append(dict(item))
            if len(result) >= max(1, int(limit)):
                break
        return result

    def active_records(self) -> list[dict[str, Any]]:
        return self.list_records(
            limit=self.max_records,
            statuses=set(ACTIVE_STRATEGIC_EXECUTION_STATES),
        )

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
        policy = StrategicExecutionPolicy.from_dict({
            **payload["policy"],
            **dict(updates),
            "max_active_executions": 1,
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
        item["created_at"] = str(item.get("created_at", "") or self._now())
        payload["history"].append(item)
        limit = min(
            self.max_history,
            int(payload["policy"].get("max_history", self.max_history)),
        )
        payload["history"] = payload["history"][-limit:]
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

    def summary(self) -> dict[str, Any]:
        records = self.list_records(limit=self.max_records)
        counts: dict[str, int] = {}
        for item in records:
            status = str(item.get("status", "UNKNOWN")).upper()
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(records),
            "active": sum(
                counts.get(state, 0)
                for state in ACTIVE_STRATEGIC_EXECUTION_STATES
            ),
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0),
            "cancelled": counts.get("CANCELLED", 0),
            "deferred": counts.get("DEFERRED_CONSTRAINTS", 0),
            "waiting_approval": counts.get("WAITING_APPROVAL", 0),
            "counts": counts,
            "path": str(self.path),
        }

    def compact(self) -> dict[str, Any]:
        payload = self.load()
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return self.summary()

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": "",
            "records": {},
            "order": [],
            "runtime": {
                "enabled": True,
                "paused": False,
                "phase": "IDLE",
                "cycles_completed": 0,
                "active_execution_id": "",
                "active_job_id": "",
                "active_goal_id": "",
                "last_opportunity_id": "",
                "last_outcome": {},
                "completed_total": 0,
                "failed_total": 0,
                "deferred_total": 0,
                "waiting_approval_total": 0,
                "last_error": "",
                "updated_at": "",
            },
            "policy": StrategicExecutionPolicy().to_dict(),
            "history": [],
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        records_source = source.get("records", {})
        records_source = (
            records_source if isinstance(records_source, dict) else {}
        )
        records = {
            str(key): cls._compact_record(
                StrategicExecutionRecord.from_dict(dict(item)).to_dict()
            )
            for key, item in records_source.items()
            if isinstance(item, dict)
        }
        order = [
            str(item)
            for item in source.get("order", [])
            if str(item) in records
        ] if isinstance(source.get("order"), list) else []
        for execution_id in records:
            if execution_id not in order:
                order.append(execution_id)
        runtime = source.get("runtime", {})
        history = source.get("history", [])
        return {
            "version": 1,
            "updated_at": str(source.get("updated_at", "")),
            "records": records,
            "order": order,
            "runtime": cls._compact_runtime({
                **cls._default_payload()["runtime"],
                **(dict(runtime) if isinstance(runtime, dict) else {}),
            }),
            "policy": StrategicExecutionPolicy.from_dict(
                source.get("policy")
                if isinstance(source.get("policy"), dict)
                else {}
            ).to_dict(),
            "history": [
                cls._compact_history(dict(item))
                for item in history[-5000:]
                if isinstance(item, dict)
            ] if isinstance(history, list) else [],
        }

    @staticmethod
    def _compact_record(value: dict[str, Any]) -> dict[str, Any]:
        result = StrategicExecutionRecord.from_dict(value).to_dict()
        for key, limit in (
            ("execution_id", 200),
            ("goal_id", 200),
            ("opportunity_id", 200),
            ("job_id", 200),
            ("status", 100),
            ("target", 2000),
            ("objective", 5000),
            ("outcome_category", 200),
            ("last_error", 4000),
        ):
            result[key] = str(result.get(key, ""))[:limit]
        metadata = result.get("metadata", {})
        result["metadata"] = (
            {
                str(key)[:100]: (
                    item[:2000]
                    if isinstance(item, str)
                    else item
                    if isinstance(item, (bool, int, float)) or item is None
                    else str(item)[:2000]
                )
                for key, item in list(metadata.items())[:100]
            }
            if isinstance(metadata, dict)
            else {}
        )
        return result

    @staticmethod
    def _compact_runtime(value: dict[str, Any]) -> dict[str, Any]:
        result = dict(value)
        result["enabled"] = bool(result.get("enabled", True))
        result["paused"] = bool(result.get("paused", False))
        for key, limit in (
            ("phase", 100),
            ("active_execution_id", 200),
            ("active_job_id", 200),
            ("active_goal_id", 200),
            ("last_opportunity_id", 200),
            ("last_error", 4000),
        ):
            result[key] = str(result.get(key, ""))[:limit]
        for key in (
            "cycles_completed",
            "completed_total",
            "failed_total",
            "deferred_total",
            "waiting_approval_total",
        ):
            result[key] = max(0, int(result.get(key, 0) or 0))
        outcome = result.get("last_outcome", {})
        result["last_outcome"] = (
            StrategicExecutionStore._compact_mapping(outcome)
            if isinstance(outcome, dict)
            else {}
        )
        return result

    @staticmethod
    def _compact_history(value: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "status",
            "success",
            "phase",
            "execution_id",
            "goal_id",
            "opportunity_id",
            "job_id",
            "outcome",
            "error",
            "created_at",
        )
        return {
            key: (
                bool(value.get(key, False))
                if key == "success"
                else str(value.get(key, ""))[:4000]
            )
            for key in allowed
            if key in value
        }

    @staticmethod
    def _compact_mapping(value: dict[str, Any]) -> dict[str, Any]:
        return {
            str(key)[:100]: (
                item[:2000]
                if isinstance(item, str)
                else item
                if isinstance(item, (bool, int, float)) or item is None
                else str(item)[:2000]
            )
            for key, item in list(value.items())[:100]
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

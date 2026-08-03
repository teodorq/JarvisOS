from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .strategic_policy_evolution_models import (
    StrategicPolicyEvolutionPolicy,
    StrategicPolicyRevision,
)


class StrategicPolicyEvolutionStore:
    """Atomic persistence for B60 policy learning and rollback."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_history: int = 1000,
        max_revisions: int = 100,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.autodev_data / "strategic_policy_evolution.json"
        self.max_history = min(5000, max(100, int(max_history)))
        self.max_revisions = min(1000, max(10, int(max_revisions)))
        self._store = JsonStore(self.path, self._default_payload)

    def load(self) -> dict[str, Any]:
        return self._payload(self._store.load())

    def runtime(self) -> dict[str, Any]:
        return dict(self.load()["runtime"])

    def update_runtime(self, updates: dict[str, Any]) -> dict[str, Any]:
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

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        payload = self.load()
        policy = StrategicPolicyEvolutionPolicy.from_dict({
            **payload["policy"],
            **dict(updates),
            "auto_approve": False,
        }).to_dict()
        payload["policy"] = policy
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(policy)

    def save_revision(
        self,
        revision: StrategicPolicyRevision | dict[str, Any],
    ) -> dict[str, Any]:
        item = (
            revision
            if isinstance(revision, StrategicPolicyRevision)
            else StrategicPolicyRevision.from_dict(dict(revision))
        )
        value = self._compact_revision(item.to_dict())
        revision_id = str(value.get("revision_id", "")).strip()
        if not revision_id:
            raise ValueError("Wersja polityki wymaga revision_id.")
        payload = self.load()
        payload["revisions"][revision_id] = value
        order = payload["revision_order"]
        if revision_id in order:
            order.remove(revision_id)
        order.append(revision_id)
        limit = min(
            self.max_revisions,
            int(payload["policy"].get("max_revisions", self.max_revisions)),
        )
        while len(order) > limit:
            removable = next(
                (
                    item_id for item_id in order
                    if str(payload["revisions"].get(item_id, {}).get("status", ""))
                    not in {"ACTIVE", "PROPOSED"}
                ),
                order[0],
            )
            order.remove(removable)
            payload["revisions"].pop(removable, None)
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def get_revision(self, revision_id: str) -> dict[str, Any] | None:
        item = self.load()["revisions"].get(str(revision_id).strip())
        return dict(item) if isinstance(item, dict) else None

    def list_revisions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self.load()
        values: list[dict[str, Any]] = []
        for revision_id in reversed(payload["revision_order"]):
            item = payload["revisions"].get(revision_id)
            if isinstance(item, dict):
                values.append(dict(item))
            if len(values) >= max(1, int(limit)):
                break
        return values

    def active_revision(self) -> dict[str, Any] | None:
        revision_id = str(self.runtime().get("active_revision_id", ""))
        if revision_id:
            return self.get_revision(revision_id)
        for item in self.list_revisions(limit=self.max_revisions):
            if str(item.get("status", "")).upper() == "ACTIVE":
                return item
        return None

    def previous_active_revision(self) -> dict[str, Any] | None:
        active_id = str(self.runtime().get("active_revision_id", ""))
        seen_active = False
        for item in self.list_revisions(limit=self.max_revisions):
            revision_id = str(item.get("revision_id", ""))
            if revision_id == active_id:
                seen_active = True
                continue
            if seen_active and str(item.get("status", "")).upper() in {
                "ACTIVE", "SUPERSEDED"
            }:
                return item
        return None

    def record_history(self, value: dict[str, Any]) -> dict[str, Any]:
        payload = self.load()
        item = self._compact_history(dict(value))
        item["created_at"] = str(item.get("created_at") or self._now())
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
        return [dict(item) for item in reversed(values) if isinstance(item, dict)]

    def mark_observed(self, execution_id: str) -> bool:
        key = str(execution_id).strip()
        if not key:
            return False
        payload = self.load()
        values = payload["observed_execution_ids"]
        if key in values:
            return False
        values.append(key)
        payload["observed_execution_ids"] = values[-5000:]
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return True

    def summary(self) -> dict[str, Any]:
        payload = self.load()
        statuses: dict[str, int] = {}
        for item in payload["revisions"].values():
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "UNKNOWN")).upper()
            statuses[status] = statuses.get(status, 0) + 1
        runtime = payload["runtime"]
        return {
            "revisions": len(payload["revisions"]),
            "active": statuses.get("ACTIVE", 0),
            "proposed": statuses.get("PROPOSED", 0),
            "rolled_back": statuses.get("ROLLED_BACK", 0),
            "observed_executions": len(payload["observed_execution_ids"]),
            "cycles_completed": int(runtime.get("cycles_completed", 0)),
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
            "runtime": {
                "enabled": False,
                "paused": False,
                "running": False,
                "phase": "IDLE",
                "cycles_completed": 0,
                "last_learning_at": "",
                "last_observed_execution_id": "",
                "last_evidence_signature": "",
                "last_observation_count": 0,
                "active_revision_id": "",
                "proposed_revision_id": "",
                "last_decision": "",
                "last_metrics": {},
                "last_result": {},
                "last_error": "",
                "updated_at": "",
            },
            "policy": StrategicPolicyEvolutionPolicy().to_dict(),
            "revisions": {},
            "revision_order": [],
            "observed_execution_ids": [],
            "history": [],
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        revisions_source = source.get("revisions", {})
        revisions_source = revisions_source if isinstance(revisions_source, dict) else {}
        revisions = {
            str(key): cls._compact_revision(
                StrategicPolicyRevision.from_dict(dict(item)).to_dict()
            )
            for key, item in revisions_source.items()
            if isinstance(item, dict)
        }
        order = [
            str(item) for item in source.get("revision_order", [])
            if str(item) in revisions
        ] if isinstance(source.get("revision_order"), list) else []
        for revision_id in revisions:
            if revision_id not in order:
                order.append(revision_id)
        runtime = source.get("runtime", {})
        history = source.get("history", [])
        observed = source.get("observed_execution_ids", [])
        return {
            "version": 1,
            "updated_at": str(source.get("updated_at", "")),
            "runtime": cls._compact_runtime({
                **cls._default_payload()["runtime"],
                **(dict(runtime) if isinstance(runtime, dict) else {}),
            }),
            "policy": StrategicPolicyEvolutionPolicy.from_dict(
                source.get("policy") if isinstance(source.get("policy"), dict) else {}
            ).to_dict(),
            "revisions": revisions,
            "revision_order": order,
            "observed_execution_ids": [
                str(item)[:200] for item in observed[-5000:] if str(item).strip()
            ] if isinstance(observed, list) else [],
            "history": [
                cls._compact_history(dict(item))
                for item in history[-5000:]
                if isinstance(item, dict)
            ] if isinstance(history, list) else [],
        }

    @staticmethod
    def _compact_runtime(value: dict[str, Any]) -> dict[str, Any]:
        result = dict(value)
        for key, limit in (
            ("phase", 100), ("last_observed_execution_id", 200),
            ("last_evidence_signature", 200),
            ("active_revision_id", 200), ("proposed_revision_id", 200),
            ("last_decision", 100), ("last_error", 4000),
        ):
            result[key] = str(result.get(key, ""))[:limit]
        result["cycles_completed"] = max(0, int(result.get("cycles_completed", 0) or 0))
        result["last_observation_count"] = max(
            0, int(result.get("last_observation_count", 0) or 0)
        )
        result["last_metrics"] = dict(result.get("last_metrics", {}) or {})
        result["last_result"] = {
            str(key)[:100]: value
            for key, value in list(dict(result.get("last_result", {}) or {}).items())[:80]
            if isinstance(value, (str, bool, int, float)) or value is None
        }
        return result

    @staticmethod
    def _compact_revision(value: dict[str, Any]) -> dict[str, Any]:
        result = StrategicPolicyRevision.from_dict(value).to_dict()
        for key, limit in (
            ("revision_id", 200), ("parent_revision_id", 200),
            ("status", 100), ("reason", 4000),
            ("created_at", 100), ("applied_at", 100), ("rolled_back_at", 100),
        ):
            result[key] = str(result.get(key, ""))[:limit]
        return result

    @staticmethod
    def _compact_history(value: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "status", "success", "phase", "revision_id", "decision",
            "reason", "execution_id", "error", "created_at",
        )
        return {
            key: (
                bool(value.get(key, False)) if key == "success"
                else str(value.get(key, ""))[:4000]
            )
            for key in allowed if key in value
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

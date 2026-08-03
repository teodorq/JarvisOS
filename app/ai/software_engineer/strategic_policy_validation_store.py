from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .strategic_policy_validation_models import (
    StrategicPolicyExperiment,
    StrategicPolicyValidationPolicy,
)


class StrategicPolicyValidationStore:
    """Atomic persistence for B61 shadow validation and promotion."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_history: int = 1000,
        max_experiments: int = 200,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.autodev_data / "strategic_policy_validation.json"
        self.max_history = min(5000, max(100, int(max_history)))
        self.max_experiments = min(1000, max(10, int(max_experiments)))
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
        payload["policy"] = StrategicPolicyValidationPolicy.from_dict({
            **payload["policy"],
            **dict(updates),
            "auto_approve": False,
        }).to_dict()
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(payload["policy"])

    def save_experiment(
        self,
        experiment: StrategicPolicyExperiment | dict[str, Any],
    ) -> dict[str, Any]:
        item = (
            experiment
            if isinstance(experiment, StrategicPolicyExperiment)
            else StrategicPolicyExperiment.from_dict(dict(experiment))
        )
        value = self._compact_experiment(item.to_dict())
        experiment_id = str(value.get("experiment_id", "")).strip()
        if not experiment_id:
            raise ValueError("Eksperyment B61 wymaga experiment_id.")
        payload = self.load()
        payload["experiments"][experiment_id] = value
        order = payload["experiment_order"]
        if experiment_id in order:
            order.remove(experiment_id)
        order.append(experiment_id)
        limit = min(
            self.max_experiments,
            int(payload["policy"].get("max_experiments", self.max_experiments)),
        )
        while len(order) > limit:
            removable = next(
                (
                    key for key in order
                    if str(payload["experiments"].get(key, {}).get("status", ""))
                    not in {"PASSED", "PROMOTED"}
                ),
                order[0],
            )
            order.remove(removable)
            payload["experiments"].pop(removable, None)
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        item = self.load()["experiments"].get(str(experiment_id).strip())
        return dict(item) if isinstance(item, dict) else None

    def latest_for_revision(
        self,
        revision_id: str,
        evidence_signature: str = "",
    ) -> dict[str, Any] | None:
        revision_id = str(revision_id).strip()
        signature = str(evidence_signature).strip()
        for item in self.list_experiments(limit=self.max_experiments):
            if str(item.get("revision_id", "")) != revision_id:
                continue
            if signature and str(item.get("evidence_signature", "")) != signature:
                continue
            return item
        return None

    def list_experiments(self, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self.load()
        values: list[dict[str, Any]] = []
        for experiment_id in reversed(payload["experiment_order"]):
            item = payload["experiments"].get(experiment_id)
            if isinstance(item, dict):
                values.append(dict(item))
            if len(values) >= max(1, int(limit)):
                break
        return values

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

    def summary(self) -> dict[str, Any]:
        payload = self.load()
        statuses: dict[str, int] = {}
        for item in payload["experiments"].values():
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "UNKNOWN")).upper()
            statuses[status] = statuses.get(status, 0) + 1
        runtime = payload["runtime"]
        return {
            "experiments": len(payload["experiments"]),
            "passed": statuses.get("PASSED", 0),
            "promoted": statuses.get("PROMOTED", 0),
            "rejected": statuses.get("REJECTED", 0),
            "held": statuses.get("INSUFFICIENT_EVIDENCE", 0),
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
                "last_validation_at": "",
                "last_experiment_id": "",
                "last_revision_id": "",
                "last_decision": "",
                "last_metrics": {},
                "last_result": {},
                "last_error": "",
                "updated_at": "",
            },
            "policy": StrategicPolicyValidationPolicy().to_dict(),
            "experiments": {},
            "experiment_order": [],
            "history": [],
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        experiments_source = source.get("experiments", {})
        experiments_source = (
            experiments_source if isinstance(experiments_source, dict) else {}
        )
        experiments = {
            str(key): cls._compact_experiment(
                StrategicPolicyExperiment.from_dict(dict(item)).to_dict()
            )
            for key, item in experiments_source.items()
            if isinstance(item, dict)
        }
        order = [
            str(item) for item in source.get("experiment_order", [])
            if str(item) in experiments
        ] if isinstance(source.get("experiment_order"), list) else []
        for experiment_id in experiments:
            if experiment_id not in order:
                order.append(experiment_id)
        runtime = source.get("runtime", {})
        history = source.get("history", [])
        return {
            "version": 1,
            "updated_at": str(source.get("updated_at", "")),
            "runtime": cls._compact_runtime({
                **cls._default_payload()["runtime"],
                **(dict(runtime) if isinstance(runtime, dict) else {}),
            }),
            "policy": StrategicPolicyValidationPolicy.from_dict(
                source.get("policy") if isinstance(source.get("policy"), dict) else {}
            ).to_dict(),
            "experiments": experiments,
            "experiment_order": order,
            "history": [
                cls._compact_history(dict(item))
                for item in history[-5000:]
                if isinstance(item, dict)
            ] if isinstance(history, list) else [],
        }

    @staticmethod
    def _compact_runtime(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "enabled": bool(value.get("enabled", False)),
            "paused": bool(value.get("paused", False)),
            "running": bool(value.get("running", False)),
            "phase": str(value.get("phase", "IDLE"))[:100],
            "cycles_completed": max(0, int(value.get("cycles_completed", 0) or 0)),
            "last_validation_at": str(value.get("last_validation_at", ""))[:100],
            "last_experiment_id": str(value.get("last_experiment_id", ""))[:200],
            "last_revision_id": str(value.get("last_revision_id", ""))[:200],
            "last_decision": str(value.get("last_decision", ""))[:100],
            "last_metrics": dict(value.get("last_metrics", {}) or {}),
            "last_result": dict(value.get("last_result", {}) or {}),
            "last_error": str(value.get("last_error", ""))[-4000:],
            "updated_at": str(value.get("updated_at", ""))[:100],
        }

    @staticmethod
    def _compact_experiment(value: dict[str, Any]) -> dict[str, Any]:
        return StrategicPolicyExperiment.from_dict(value).to_dict()

    @staticmethod
    def _compact_history(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": str(value.get("status", "UNKNOWN"))[:100],
            "success": bool(value.get("success", False)),
            "phase": str(value.get("phase", ""))[:100],
            "experiment_id": str(value.get("experiment_id", ""))[:200],
            "revision_id": str(value.get("revision_id", ""))[:200],
            "decision": str(value.get("decision", ""))[:100],
            "reason": str(value.get("reason", ""))[-2000:],
            "error": str(value.get("error", ""))[-2000:],
            "created_at": str(value.get("created_at", ""))[:100],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

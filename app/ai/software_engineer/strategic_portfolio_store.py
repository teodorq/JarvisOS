from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .strategic_portfolio_models import (
    StrategicPortfolioEntry,
    StrategicPortfolioPolicy,
)


class StrategicPortfolioStore:
    """Atomic persistent state for B59 adaptive strategic portfolio."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_history: int = 1000,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.autodev_data / "strategic_portfolio.json"
        self.max_history = min(5000, max(100, int(max_history)))
        self._store = JsonStore(self.path, self._default_payload)

    def load(self) -> dict[str, Any]:
        return self._payload(self._store.load())

    def save_entry(
        self,
        entry: StrategicPortfolioEntry | dict[str, Any],
    ) -> dict[str, Any]:
        item = (
            entry
            if isinstance(entry, StrategicPortfolioEntry)
            else StrategicPortfolioEntry.from_dict(dict(entry))
        )
        value = self._compact_entry(item.to_dict())
        goal_id = str(value.get("goal_id", "")).strip()
        if not goal_id:
            raise ValueError("Wpis portfolio strategicznego wymaga goal_id.")
        payload = self.load()
        existing = payload["entries"].get(goal_id, {})
        if str(existing.get("created_at", "")).strip():
            value["created_at"] = str(existing["created_at"])
        value["updated_at"] = self._now()
        payload["entries"][goal_id] = value
        order = payload["order"]
        if goal_id in order:
            order.remove(goal_id)
        order.append(goal_id)
        limit = int(payload["policy"].get("max_entries", 200))
        while len(order) > limit:
            removable = next(
                (
                    item_id
                    for item_id in order
                    if str(
                        payload["entries"].get(item_id, {}).get(
                            "status", ""
                        )
                    ).upper()
                    in {"BLOCKED", "COMPLETED", "REJECTED"}
                ),
                order[0],
            )
            order.remove(removable)
            payload["entries"].pop(removable, None)
        payload["updated_at"] = value["updated_at"]
        self._store.save(payload)
        return dict(value)

    def replace_entries(
        self,
        entries: list[StrategicPortfolioEntry | dict[str, Any]],
    ) -> list[dict[str, Any]]:
        incoming: set[str] = set()
        for entry in entries:
            saved = self.save_entry(entry)
            incoming.add(str(saved.get("goal_id", "")))
        payload = self.load()
        for goal_id in list(payload["entries"]):
            if goal_id in incoming:
                continue
            payload["entries"].pop(goal_id, None)
            if goal_id in payload["order"]:
                payload["order"].remove(goal_id)
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return self.list_entries(limit=1000)

    def get_entry(self, goal_id: str) -> dict[str, Any] | None:
        value = self.load()["entries"].get(str(goal_id).strip())
        return dict(value) if isinstance(value, dict) else None

    def list_entries(
        self,
        *,
        limit: int = 100,
        statuses: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.load()
        allowed = {str(item).upper() for item in (statuses or set())}
        result: list[dict[str, Any]] = []
        for goal_id in reversed(payload["order"]):
            item = payload["entries"].get(goal_id)
            if not isinstance(item, dict):
                continue
            if allowed and str(item.get("status", "")).upper() not in allowed:
                continue
            result.append(dict(item))
            if len(result) >= max(1, int(limit)):
                break
        result.sort(
            key=lambda item: (
                str(item.get("status", "")).upper() == "READY",
                float(item.get("adaptive_priority_score", 0.0) or 0.0),
                float(item.get("confidence", 0.0) or 0.0),
                -float(item.get("risk_score", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return result

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
        policy = StrategicPortfolioPolicy.from_dict({
            **payload["policy"],
            **dict(updates),
            "max_active_goals": 1,
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

    def summary(self) -> dict[str, Any]:
        entries = self.list_entries(limit=1000)
        counts: dict[str, int] = {}
        for entry in entries:
            status = str(entry.get("status", "UNKNOWN")).upper()
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(entries),
            "ready": counts.get("READY", 0),
            "active": counts.get("ACTIVE", 0),
            "waiting_approval": counts.get("WAITING_APPROVAL", 0),
            "cooldown": counts.get("COOLDOWN", 0),
            "blocked": counts.get("BLOCKED", 0),
            "completed": counts.get("COMPLETED", 0),
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
            "entries": {},
            "order": [],
            "runtime": {
                "enabled": False,
                "paused": False,
                "running": False,
                "phase": "IDLE",
                "cycles_completed": 0,
                "last_rebalance_at": "",
                "selected_goal_id": "",
                "last_selected_subsystem": "",
                "last_execution_id": "",
                "last_outcome": "",
                "last_result": {},
                "last_error": "",
                "updated_at": "",
            },
            "policy": StrategicPortfolioPolicy().to_dict(),
            "history": [],
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        entries_source = source.get("entries", {})
        entries_source = (
            entries_source if isinstance(entries_source, dict) else {}
        )
        entries = {
            str(key): cls._compact_entry(
                StrategicPortfolioEntry.from_dict(dict(item)).to_dict()
            )
            for key, item in entries_source.items()
            if isinstance(item, dict)
        }
        order = [
            str(item)
            for item in source.get("order", [])
            if str(item) in entries
        ] if isinstance(source.get("order"), list) else []
        for goal_id in entries:
            if goal_id not in order:
                order.append(goal_id)
        runtime = source.get("runtime", {})
        history = source.get("history", [])
        return {
            "version": 1,
            "updated_at": str(source.get("updated_at", "")),
            "entries": entries,
            "order": order,
            "runtime": cls._compact_runtime({
                **cls._default_payload()["runtime"],
                **(dict(runtime) if isinstance(runtime, dict) else {}),
            }),
            "policy": StrategicPortfolioPolicy.from_dict(
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
    def _compact_entry(value: dict[str, Any]) -> dict[str, Any]:
        result = StrategicPortfolioEntry.from_dict(value).to_dict()
        for key, limit in (
            ("goal_id", 200),
            ("subsystem", 1000),
            ("issue_type", 200),
            ("title", 500),
            ("status", 100),
            ("last_execution_id", 200),
            ("last_outcome", 100),
            ("cooldown_until", 100),
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
        for key, limit in (
            ("phase", 100),
            ("selected_goal_id", 200),
            ("last_selected_subsystem", 1000),
            ("last_execution_id", 200),
            ("last_outcome", 100),
            ("last_error", 4000),
        ):
            result[key] = str(result.get(key, ""))[:limit]
        result["cycles_completed"] = max(
            0,
            int(result.get("cycles_completed", 0) or 0),
        )
        last_result = result.get("last_result", {})
        result["last_result"] = (
            {
                str(key)[:100]: (
                    item[:4000] if isinstance(item, str) else item
                )
                for key, item in list(last_result.items())[:80]
                if isinstance(item, (str, bool, int, float)) or item is None
            }
            if isinstance(last_result, dict)
            else {}
        )
        return result

    @staticmethod
    def _compact_history(value: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "status",
            "success",
            "phase",
            "goal_id",
            "execution_id",
            "outcome",
            "reason",
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
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

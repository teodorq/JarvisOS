from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .project_intelligence_models import (
    ProjectIntelligencePolicy,
    ProjectOpportunity,
)


class ProjectIntelligenceStore:
    """Atomic, bounded state for B55 self-directed development."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_cycles: int = 500,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = (
            self.paths.autodev_data
            / "project_intelligence.json"
        )
        self.max_cycles = min(5000, max(50, int(max_cycles)))
        self._store = JsonStore(self.path, self._default_payload)

    def load(self) -> dict[str, Any]:
        return self._payload(self._store.load())

    def save_opportunity(
        self,
        opportunity: ProjectOpportunity | dict[str, Any],
    ) -> dict[str, Any]:
        item = (
            opportunity
            if isinstance(opportunity, ProjectOpportunity)
            else ProjectOpportunity.from_dict(dict(opportunity))
        )
        value = item.to_dict()
        opportunity_id = str(value.get("opportunity_id", "")).strip()
        if not opportunity_id:
            raise ValueError("Opportunity wymaga opportunity_id.")
        payload = self.load()
        existing = payload["opportunities"].get(opportunity_id, {})
        created_at = str(existing.get("created_at", "")).strip()
        if created_at:
            value["created_at"] = created_at
        value["updated_at"] = self._now()
        payload["opportunities"][opportunity_id] = self._compact(value)
        order = payload["order"]
        if opportunity_id in order:
            order.remove(opportunity_id)
        order.append(opportunity_id)
        max_backlog = int(payload["policy"].get("max_backlog", 200))
        while len(order) > max_backlog:
            removable = next(
                (
                    item_id
                    for item_id in order
                    if str(
                        payload["opportunities"]
                        .get(item_id, {})
                        .get("status", "")
                    ).upper()
                    in {
                        "COMPLETED",
                        "FAILED",
                        "CANCELLED",
                        "REJECTED",
                    }
                ),
                order[0],
            )
            order.remove(removable)
            payload["opportunities"].pop(removable, None)
        payload["updated_at"] = value["updated_at"]
        self._store.save(payload)
        return dict(payload["opportunities"][opportunity_id])

    def upsert_by_fingerprint(
        self,
        opportunity: ProjectOpportunity | dict[str, Any],
    ) -> dict[str, Any]:
        item = (
            opportunity
            if isinstance(opportunity, ProjectOpportunity)
            else ProjectOpportunity.from_dict(dict(opportunity))
        )
        existing = self.find_by_fingerprint(item.fingerprint)
        if existing is not None:
            current = ProjectOpportunity.from_dict(existing)
            current.title = item.title
            current.objective = item.objective
            current.target = item.target
            current.source = item.source
            current.severity = item.severity
            current.issue_type = item.issue_type
            current.value_score = item.value_score
            current.risk_score = item.risk_score
            current.effort_score = item.effort_score
            current.confidence = item.confidence
            current.final_score = item.final_score
            current.metadata = {
                **current.metadata,
                **item.metadata,
            }
            return self.save_opportunity(current)
        return self.save_opportunity(item)

    def find_by_fingerprint(
        self,
        fingerprint: str,
    ) -> dict[str, Any] | None:
        key = str(fingerprint).strip().casefold()
        if not key:
            return None
        for item in self.list_opportunities(limit=1000):
            if str(item.get("fingerprint", "")).casefold() == key:
                return item
        return None

    def get_opportunity(
        self,
        opportunity_id: str,
    ) -> dict[str, Any] | None:
        value = self.load()["opportunities"].get(
            str(opportunity_id).strip()
        )
        return dict(value) if isinstance(value, dict) else None

    def list_opportunities(
        self,
        *,
        limit: int = 100,
        statuses: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.load()
        allowed = {str(item).upper() for item in (statuses or set())}
        result: list[dict[str, Any]] = []
        for opportunity_id in reversed(payload["order"]):
            item = payload["opportunities"].get(opportunity_id)
            if not isinstance(item, dict):
                continue
            if allowed and str(item.get("status", "")).upper() not in allowed:
                continue
            result.append(dict(item))
            if len(result) >= max(1, int(limit)):
                break
        return result

    def update_opportunity(
        self,
        opportunity_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        current = self.get_opportunity(opportunity_id)
        if current is None:
            return None
        value = ProjectOpportunity.from_dict({
            **current,
            **dict(updates),
        })
        return self.save_opportunity(value)

    def record_cycle(
        self,
        cycle: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.load()
        value = self._compact_cycle(dict(cycle))
        value["created_at"] = str(
            value.get("created_at", "")
            or self._now()
        )
        payload["cycles"].append(value)
        payload["cycles"] = payload["cycles"][-self.max_cycles:]
        payload["updated_at"] = value["created_at"]
        self._store.save(payload)
        return dict(value)

    def cycles(self, *, limit: int = 20) -> list[dict[str, Any]]:
        values = self.load()["cycles"][-max(1, int(limit)):]
        return [
            dict(item)
            for item in reversed(values)
            if isinstance(item, dict)
        ]

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
        policy = ProjectIntelligencePolicy.from_dict({
            **payload["policy"],
            **dict(updates),
            "auto_approve": False,
        }).to_dict()
        payload["policy"] = policy
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(policy)

    def summary(self) -> dict[str, Any]:
        items = self.list_opportunities(limit=1000)
        counts: dict[str, int] = {}
        for item in items:
            state = str(item.get("status", "UNKNOWN")).upper()
            counts[state] = counts.get(state, 0) + 1
        return {
            "total": len(items),
            "counts": counts,
            "active": sum(
                counts.get(state, 0)
                for state in (
                    "DISPATCHED",
                    "RUNNING",
                    "WAITING_APPROVAL",
                    "WAITING_RESOURCES",
                )
            ),
            "pending": counts.get("PENDING", 0),
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0),
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
            "opportunities": {},
            "order": [],
            "cycles": [],
            "runtime": {
                "enabled": False,
                "paused": False,
                "running": False,
                "cycles_completed": 0,
                "last_scan_at": "",
                "last_dispatch_at": "",
                "last_error": "",
                "updated_at": "",
            },
            "policy": ProjectIntelligencePolicy().to_dict(),
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        opportunities = source.get("opportunities", {})
        opportunities = opportunities if isinstance(opportunities, dict) else {}
        normalized = {
            str(key): cls._compact(
                ProjectOpportunity.from_dict(dict(item)).to_dict()
            )
            for key, item in opportunities.items()
            if isinstance(item, dict)
        }
        order = [
            str(item)
            for item in source.get("order", [])
            if str(item) in normalized
        ] if isinstance(source.get("order"), list) else []
        for key in normalized:
            if key not in order:
                order.append(key)
        runtime = source.get("runtime", {})
        runtime = dict(runtime) if isinstance(runtime, dict) else {}
        cycles = source.get("cycles", [])
        cycles = [
            cls._compact_cycle(dict(item))
            for item in cycles[-5000:]
            if isinstance(item, dict)
        ] if isinstance(cycles, list) else []
        return {
            "version": 1,
            "updated_at": str(source.get("updated_at", "")),
            "opportunities": normalized,
            "order": order,
            "cycles": cycles,
            "runtime": {
                **cls._default_payload()["runtime"],
                **runtime,
            },
            "policy": ProjectIntelligencePolicy.from_dict(
                source.get("policy")
                if isinstance(source.get("policy"), dict)
                else {}
            ).to_dict(),
        }

    @staticmethod
    def _compact(value: dict[str, Any]) -> dict[str, Any]:
        result = ProjectOpportunity.from_dict(value).to_dict()
        for key, limit in (
            ("title", 500),
            ("objective", 5000),
            ("target", 1000),
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
    def _compact_cycle(value: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "status",
            "success",
            "scanned",
            "created",
            "updated",
            "selected_id",
            "dispatched_job_id",
            "reconciled",
            "errors",
            "created_at",
        )
        result = {
            key: value.get(key)
            for key in allowed
            if key in value
        }
        errors = result.get("errors", [])
        result["errors"] = (
            [str(item)[:2000] for item in errors[:20]]
            if isinstance(errors, list)
            else []
        )
        return result

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

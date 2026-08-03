from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.stability.common import bounded, sha256_json, utc_iso


Snapshot = Callable[[], dict[str, Any]]
Action = Callable[[], Any]
Restore = Callable[[dict[str, Any]], Any]


class SafeServiceRestartCenter:
    """B114 explicit restart plans with checkpoint and state restoration."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.project_root / "data" / "stability" / "service_restarts.json",
            lambda: {"plans": [], "executions": []},
        )
        self._registry: dict[str, tuple[Snapshot, Action, Restore]] = {}

    def register(self, name: str, snapshot: Snapshot, restart: Action, restore: Restore) -> None:
        self._registry[self._name(name)] = (snapshot, restart, restore)

    def prepare(self, name: str) -> dict[str, Any]:
        service = self._name(name)
        adapter = self._registry.get(service)
        if adapter is None:
            raise ValueError(f"B114: usługa {service} nie jest zarejestrowana.")
        checkpoint = dict(adapter[0]() or {})
        plan = {
            "plan_id": uuid4().hex[:16],
            "service": service,
            "status": "PREPARED",
            "created_at": utc_iso(),
            "checkpoint": checkpoint,
            "checkpoint_sha256": sha256_json(checkpoint),
        }
        state = self.store.load()
        state["plans"] = bounded(list(state.get("plans", [])) + [plan], 50)
        self.store.save(state)
        return plan

    def execute(self, plan_id: str | None = None) -> dict[str, Any]:
        state = self.store.load()
        plans = list(state.get("plans", []))
        plan = self._find_plan(plans, plan_id)
        adapter = self._registry.get(str(plan.get("service", "")))
        if adapter is None:
            raise ValueError("B114: adapter restartu nie jest dostępny.")
        adapter[1]()
        adapter[2](dict(plan.get("checkpoint", {}) or {}))
        restored = dict(adapter[0]() or {})
        verified = sha256_json(restored) == str(plan.get("checkpoint_sha256", ""))
        plan["status"] = "COMPLETED" if verified else "FAILED"
        plan["completed_at"] = utc_iso()
        execution = {
            "plan_id": plan["plan_id"],
            "service": plan["service"],
            "status": plan["status"],
            "state_restored": verified,
            "created_at": plan["completed_at"],
        }
        state["plans"] = plans
        state["executions"] = bounded(list(state.get("executions", [])) + [execution], 50)
        self.store.save(state)
        return execution

    def status(self) -> dict[str, Any]:
        state = self.store.load()
        plans = list(state.get("plans", []))
        executions = list(state.get("executions", []))
        latest = dict(executions[-1]) if executions else {}
        return {
            "status": "SAFE_SERVICE_RESTART_READY",
            "registered_services": sorted(self._registry),
            "plan_count": len(plans),
            "execution_count": len(executions),
            "latest_status": latest.get("status", "NOT_RUN"),
            "state_restored": bool(latest.get("state_restored", False)),
            "latest_execution": latest,
        }

    @staticmethod
    def _find_plan(plans: list[dict[str, Any]], plan_id: str | None) -> dict[str, Any]:
        for plan in reversed(plans):
            if plan.get("status") == "PREPARED" and (not plan_id or plan.get("plan_id") == plan_id):
                return plan
        raise ValueError("B114: brak przygotowanego planu restartu.")

    @staticmethod
    def _name(value: object) -> str:
        return str(value or "").strip().lower().replace(" ", "_")

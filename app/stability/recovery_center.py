from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.stability.common import bounded, parse_utc, utc_iso, utc_now


class RuntimeRecoveryCenter:
    """B113 heartbeat supervision and bounded local recovery records."""

    def __init__(self, project_root: str | Path | None = None, stale_seconds: int = 120) -> None:
        self.project_root = resolve_project_root(project_root)
        self.stale_seconds = max(10, int(stale_seconds))
        self.store = JsonStore(
            self.project_root / "data" / "stability" / "runtime_recovery.json",
            lambda: {"services": {}, "incidents": [], "recoveries": []},
        )

    def heartbeat(self, service: str, status: str = "HEALTHY") -> dict[str, Any]:
        state = self.store.load()
        record = {
            "service": self._service(service),
            "status": str(status).upper(),
            "last_heartbeat": utc_iso(),
        }
        state.setdefault("services", {})[record["service"]] = record
        self.store.save(state)
        return record

    def simulate_stale(self, service: str = "voice") -> dict[str, Any]:
        state = self.store.load()
        name = self._service(service)
        stale_at = (utc_now() - timedelta(seconds=self.stale_seconds + 30)).isoformat()
        record = {"service": name, "status": "UNRESPONSIVE", "last_heartbeat": stale_at}
        state.setdefault("services", {})[name] = record
        self.store.save(state)
        return record

    def check(self) -> list[dict[str, Any]]:
        state = self.store.load()
        incidents = list(state.get("incidents", []))
        open_services = {item.get("service") for item in incidents if item.get("status") == "OPEN"}
        now = utc_now()
        created: list[dict[str, Any]] = []
        for name, service in dict(state.get("services", {}) or {}).items():
            heartbeat = parse_utc(service.get("last_heartbeat"))
            stale = heartbeat is None or (now - heartbeat).total_seconds() > self.stale_seconds
            if stale and name not in open_services:
                incident = {
                    "incident_id": uuid4().hex[:16],
                    "service": name,
                    "status": "OPEN",
                    "reason": "HEARTBEAT_STALE",
                    "created_at": utc_iso(),
                }
                incidents.append(incident)
                created.append(incident)
        state["incidents"] = bounded(incidents, 80)
        self.store.save(state)
        return created

    def recover(self, service: str | None = None) -> dict[str, Any]:
        state = self.store.load()
        incidents = list(state.get("incidents", []))
        target = self._service(service) if service else self._latest_open_service(incidents)
        if not target:
            raise ValueError("B113: brak otwartego incydentu do odzyskania.")
        now = utc_iso()
        recovered_incident = None
        for incident in reversed(incidents):
            if incident.get("service") == target and incident.get("status") == "OPEN":
                incident["status"] = "RECOVERED"
                incident["recovered_at"] = now
                recovered_incident = incident
                break
        if recovered_incident is None:
            raise ValueError(f"B113: brak otwartego incydentu usługi {target}.")
        state.setdefault("services", {})[target] = {
            "service": target,
            "status": "HEALTHY",
            "last_heartbeat": now,
        }
        recovery = {
            "service": target,
            "status": "RECOVERED",
            "created_at": now,
            "incident_id": recovered_incident["incident_id"],
        }
        state["recoveries"] = bounded(list(state.get("recoveries", [])) + [recovery], 80)
        state["incidents"] = incidents
        self.store.save(state)
        return recovery

    def status(self) -> dict[str, Any]:
        state = self.store.load()
        incidents = list(state.get("incidents", []))
        open_items = [item for item in incidents if item.get("status") == "OPEN"]
        return {
            "status": "RUNTIME_RECOVERY_READY",
            "service_count": len(dict(state.get("services", {}) or {})),
            "incident_count": len(incidents),
            "open_incident_count": len(open_items),
            "recovery_count": len(list(state.get("recoveries", []))),
            "latest_incident": dict(incidents[-1]) if incidents else {},
            "latest_recovery": dict(list(state.get("recoveries", []))[-1]) if state.get("recoveries") else {},
        }

    @staticmethod
    def _service(value: object) -> str:
        name = str(value or "runtime").strip().lower().replace(" ", "_")
        return name or "runtime"

    @staticmethod
    def _latest_open_service(incidents: list[dict[str, Any]]) -> str:
        for incident in reversed(incidents):
            if incident.get("status") == "OPEN":
                return str(incident.get("service", ""))
        return ""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import threading
from typing import Any
import uuid

from app.core.project_paths import resolve_project_root

from .autonomous_cycle_models import (
    AutonomousBacklogPolicy,
    AutonomousDevelopmentCycle,
)


class AutonomousCycleStore:
    """Atomic cycle registry, task claims, leases and duplicate protection."""

    VERSION = 1
    ACTIVE = {"SELECTING", "PREPARING", "READY_FOR_APPROVAL"}

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: AutonomousBacklogPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or AutonomousBacklogPolicy()
        self.root = self.project_root / "data" / "autodev" / "autonomous_development_2_1"
        self.registry_path = self.root / "registry.json"
        self.cycles_root = self.root / "cycles"
        self._lock = threading.RLock()

    def new_cycle(self) -> AutonomousDevelopmentCycle:
        now = self._now()
        cycle = AutonomousDevelopmentCycle(
            cycle_id="autodev-cycle-" + uuid.uuid4().hex[:16],
            status="SELECTING",
            created_at=now,
            updated_at=now,
        )
        return self.save(cycle)

    def save(self, cycle: AutonomousDevelopmentCycle) -> AutonomousDevelopmentCycle:
        with self._lock:
            cycle.updated_at = self._now()
            path = self._cycle_path(cycle.cycle_id)
            self._atomic_json(path, cycle.to_dict())
            registry = self._registry()
            cycles = dict(registry.get("cycles", {}) or {})
            cycles[cycle.cycle_id] = {
                "status": cycle.status,
                "task_id": str(cycle.task.get("task_id", "")),
                "task_fingerprint": cycle.task_fingerprint,
                "safe_session_id": cycle.safe_session_id,
                "updated_at": cycle.updated_at,
            }
            order = [item for item in list(registry.get("order", []) or []) if item != cycle.cycle_id]
            order.insert(0, cycle.cycle_id)
            registry.update({"cycles": cycles, "order": order, "latest_cycle_id": cycle.cycle_id})
            self._save_registry(registry)
            self._prune(registry)
        return cycle

    def load(self, cycle_id: str) -> AutonomousDevelopmentCycle:
        value = self._load_json(self._cycle_path(self._safe_id(cycle_id)))
        if not value:
            raise FileNotFoundError("Nie znaleziono autonomicznego cyklu AutoDev.")
        return AutonomousDevelopmentCycle.from_dict(value)

    def latest(self) -> AutonomousDevelopmentCycle | None:
        for cycle_id in list(self._registry().get("order", []) or []):
            try:
                return self.load(cycle_id)
            except (OSError, ValueError, TypeError):
                continue
        return None

    def active(self) -> AutonomousDevelopmentCycle | None:
        self.recover_stale()
        for cycle_id in list(self._registry().get("order", []) or []):
            try:
                cycle = self.load(cycle_id)
            except (OSError, ValueError, TypeError):
                continue
            if cycle.status in self.ACTIVE:
                return cycle
        return None

    def claim(self, cycle: AutonomousDevelopmentCycle, task: dict[str, Any]) -> bool:
        fingerprint = str(task.get("fingerprint", ""))
        if not fingerprint:
            return False
        with self._lock:
            registry = self._registry()
            claims = dict(registry.get("claims", {}) or {})
            current = dict(claims.get(fingerprint, {}) or {})
            if current and not self._expired(str(current.get("expires_at", ""))):
                return current.get("cycle_id") == cycle.cycle_id
            expires = datetime.now(timezone.utc) + timedelta(seconds=self.policy.lease_seconds)
            claims[fingerprint] = {
                "cycle_id": cycle.cycle_id,
                "task_id": str(task.get("task_id", "")),
                "expires_at": expires.isoformat(),
            }
            registry["claims"] = claims
            self._save_registry(registry)
        cycle.task = dict(task)
        cycle.task_fingerprint = fingerprint
        cycle.lease_expires_at = expires.isoformat()
        cycle.status = "PREPARING"
        self.save(cycle)
        return True

    def release(self, cycle: AutonomousDevelopmentCycle) -> None:
        with self._lock:
            registry = self._registry()
            claims = dict(registry.get("claims", {}) or {})
            current = dict(claims.get(cycle.task_fingerprint, {}) or {})
            if current.get("cycle_id") == cycle.cycle_id:
                claims.pop(cycle.task_fingerprint, None)
                registry["claims"] = claims
                self._save_registry(registry)

    def excluded_fingerprints(self) -> set[str]:
        self.recover_stale()
        registry = self._registry()
        claims = dict(registry.get("claims", {}) or {})
        completed = set(registry.get("completed_fingerprints", []) or [])
        deferred = {
            key for key, value in dict(registry.get("deferred", {}) or {}).items()
            if not self._expired(str(dict(value or {}).get("expires_at", "")))
        }
        active = {
            key for key, value in claims.items()
            if not self._expired(str(dict(value or {}).get("expires_at", "")))
        }
        return completed | deferred | active

    def defer(
        self,
        cycle: AutonomousDevelopmentCycle,
        reason: str,
        *,
        seconds: int = 900,
    ) -> None:
        if not cycle.task_fingerprint:
            return
        with self._lock:
            registry = self._registry()
            deferred = dict(registry.get("deferred", {}) or {})
            expires = datetime.now(timezone.utc) + timedelta(seconds=max(60, seconds))
            deferred[cycle.task_fingerprint] = {
                "task_id": str(cycle.task.get("task_id", "")),
                "reason": str(reason),
                "expires_at": expires.isoformat(),
            }
            registry["deferred"] = deferred
            self._save_registry(registry)
        self.release(cycle)

    def mark_completed(self, cycle: AutonomousDevelopmentCycle) -> None:
        if cycle.task_fingerprint:
            with self._lock:
                registry = self._registry()
                completed = set(registry.get("completed_fingerprints", []) or [])
                completed.add(cycle.task_fingerprint)
                registry["completed_fingerprints"] = sorted(completed)[-500:]
                self._save_registry(registry)
        self.release(cycle)

    def recover_stale(self) -> int:
        recovered = 0
        for cycle_id in list(self._registry().get("order", []) or []):
            try:
                cycle = self.load(cycle_id)
            except (OSError, ValueError, TypeError):
                continue
            if cycle.status not in {"SELECTING", "PREPARING"}:
                continue
            if cycle.lease_expires_at and not self._expired(cycle.lease_expires_at):
                continue
            cycle.status = "STALE"
            cycle.errors.append("Wygasła dzierżawa niedokończonego cyklu.")
            self.save(cycle)
            self.release(cycle)
            recovered += 1
        return recovered

    def _registry(self) -> dict[str, Any]:
        value = self._load_json(self.registry_path)
        return value or {
            "version": self.VERSION,
            "cycles": {},
            "order": [],
            "claims": {},
            "deferred": {},
            "completed_fingerprints": [],
            "latest_cycle_id": "",
        }

    def _save_registry(self, value: dict[str, Any]) -> None:
        value["version"] = self.VERSION
        value["updated_at"] = self._now()
        self._atomic_json(self.registry_path, value)

    def _prune(self, registry: dict[str, Any]) -> None:
        order = list(registry.get("order", []) or [])
        if len(order) <= self.policy.max_cycles:
            return
        keep = order[: self.policy.max_cycles]
        cycles = dict(registry.get("cycles", {}) or {})
        for cycle_id in order[self.policy.max_cycles:]:
            try:
                cycle = self.load(cycle_id)
            except (OSError, ValueError, TypeError):
                continue
            if cycle.status in self.ACTIVE:
                keep.append(cycle_id)
                continue
            shutil.rmtree(self._cycle_path(cycle_id).parent, ignore_errors=True)
            cycles.pop(cycle_id, None)
        registry["order"] = keep
        registry["cycles"] = cycles
        self._save_registry(registry)

    def _cycle_path(self, cycle_id: str) -> Path:
        return self.cycles_root / self._safe_id(cycle_id) / "cycle.json"

    @staticmethod
    def _safe_id(value: str) -> str:
        text = str(value).strip()
        if not text.startswith("autodev-cycle-") or not text.replace("-", "").isalnum():
            raise ValueError("Nieprawidłowy identyfikator cyklu AutoDev.")
        return text

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError):
            return {}
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _expired(value: str) -> bool:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return moment <= datetime.now(timezone.utc)
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

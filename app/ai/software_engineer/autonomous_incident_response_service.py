from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore


_TERMINAL_B68_PHASES = {
    "CIRCUIT_BREAKER",
    "CYCLE_TIMEOUT",
}
_OPEN_STATUSES = {"OPEN", "CONTAINED"}
_SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


class AutonomousIncidentResponseService:
    """B69 bounded incident detection, containment and recovery coordination."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        resource_budget: Any,
        full_autonomy: Any,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.resource_budget = resource_budget
        self.full_autonomy = full_autonomy
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._reconcile_runtime_after_restart()

    def scan(self) -> dict[str, Any]:
        with self._lock:
            policy = self.store.policy("B69")
            signals = self._detect_signals(policy)
            incidents: list[dict[str, Any]] = []
            contained: list[dict[str, Any]] = []
            active_fingerprints: set[str] = set()

            for signal in signals:
                incident = self._upsert_incident(signal, policy)
                incidents.append(incident)
                active_fingerprints.add(str(incident.get("fingerprint", "")))
                if self._should_auto_contain(incident, policy):
                    contained_incident = self._contain(incident)
                    contained.append(contained_incident)

            resolved = self._resolve_recovered(active_fingerprints, policy)
            phase = "INCIDENT" if incidents else "READY"
            decision = "CONTAIN" if contained else ("OBSERVE" if incidents else "CLEAR")
            return self._finish(
                "AUTONOMOUS_INCIDENT_SCAN_COMPLETED",
                success=True,
                phase=phase,
                decision=decision,
                incidents=incidents,
                contained=contained,
                resolved=resolved,
                detected=len(incidents),
            )

    run_cycle = scan

    def start_background(self) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return self._response(
                    "AUTONOMOUS_INCIDENT_MONITOR_ALREADY_RUNNING",
                    success=True,
                )
            self._stop_event.clear()
            self.store.update_policy("B69", {
                "enabled": True,
                "auto_approve": False,
            })
            self.store.update_runtime("B69", {
                "enabled": True,
                "running": True,
                "paused": False,
                "phase": "STARTING",
                "last_status": "AUTONOMOUS_INCIDENT_MONITOR_STARTED",
                "last_decision": "MONITOR",
                "last_error": "",
            })
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-b69-incident-monitor",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "AUTONOMOUS_INCIDENT_MONITOR_STARTED",
                success=True,
                runtime=self.store.runtime("B69"),
            )

    def stop_background(self) -> dict[str, Any]:
        with self._lock:
            self._stop_event.set()
            worker = self._thread
        if worker is not None and worker.is_alive():
            worker.join(timeout=10.0)
        worker_alive = bool(worker is not None and worker.is_alive())
        with self._lock:
            if worker is not None and not worker_alive:
                self._thread = None
            self.store.update_policy("B69", {
                "enabled": False,
                "auto_approve": False,
            })
            phase = "STOPPED_PENDING_WORKER" if worker_alive else "STOPPED"
            status = (
                "AUTONOMOUS_INCIDENT_MONITOR_STOPPED_PENDING_WORKER"
                if worker_alive
                else "AUTONOMOUS_INCIDENT_MONITOR_STOPPED"
            )
            runtime = self.store.update_runtime("B69", {
                "enabled": False,
                "running": worker_alive,
                "paused": False,
                "phase": phase,
                "last_status": status,
                "last_decision": "STOP",
                "last_error": "",
            })
            return self._response(
                status,
                success=True,
                runtime=runtime,
                worker_alive=worker_alive,
            )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime("B69", {
            "paused": True,
            "phase": "PAUSED",
        })
        return self._response(
            "AUTONOMOUS_INCIDENT_MONITOR_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume(self) -> dict[str, Any]:
        self.store.update_policy("B69", {
            "enabled": True,
            "auto_approve": False,
        })
        runtime = self.store.update_runtime("B69", {
            "enabled": True,
            "paused": False,
            "phase": "RESUMING",
        })
        if not self.is_running():
            return self.start_background()
        return self._response(
            "AUTONOMOUS_INCIDENT_MONITOR_RESUMED",
            success=True,
            runtime=runtime,
        )

    def contain_latest(self) -> dict[str, Any]:
        incident = self._latest_open_incident()
        if not incident:
            return self._response(
                "AUTONOMOUS_INCIDENT_NOT_FOUND",
                success=True,
                decision="HOLD",
                reason="Brak otwartego incydentu do ograniczenia.",
            )
        contained = self._contain(incident)
        return self._response(
            "AUTONOMOUS_INCIDENT_CONTAINED",
            success=True,
            decision="CONTAIN",
            incident=contained,
        )

    def resolve_latest(self) -> dict[str, Any]:
        records = self._chronological_incidents()
        target: dict[str, Any] | None = None
        for item in reversed(records):
            if str(item.get("status", "")).upper() in _OPEN_STATUSES:
                target = item
                break
        if target is None:
            return self._response(
                "AUTONOMOUS_INCIDENT_NOT_FOUND",
                success=True,
                decision="HOLD",
                reason="Brak otwartego incydentu do zamknięcia.",
            )
        target["status"] = "RESOLVED"
        target["resolved_at"] = self._now()
        target["resolution"] = "MANUAL_CONFIRMATION"
        self.store.replace_records("B69", records)
        self.store.record_history("B69", {
            "status": "AUTONOMOUS_INCIDENT_RESOLVED",
            "success": True,
            "phase": "READY",
            "decision": "RESOLVE",
            "reason": str(target.get("fingerprint", "")),
            "error": "",
        })
        return self._response(
            "AUTONOMOUS_INCIDENT_RESOLVED",
            success=True,
            decision="RESOLVE",
            incident=target,
        )

    def status(self) -> dict[str, Any]:
        runtime = self.store.runtime("B69")
        if (
            str(runtime.get("phase", "")) == "STOPPED_PENDING_WORKER"
            and not self.is_running()
        ):
            runtime = self.store.update_runtime("B69", {
                "running": False,
                "phase": "STOPPED",
                "last_status": "AUTONOMOUS_INCIDENT_MONITOR_STOPPED",
                "last_decision": "STOP",
                "last_error": "",
            })
        incidents = self.store.list_records("B69", limit=50)
        counts = self._incident_counts(incidents)
        return self._response(
            "AUTONOMOUS_INCIDENT_RESPONSE_STATUS",
            success=True,
            runtime=runtime,
            incidents=incidents,
            incident_counts=counts,
            resource_status=self.resource_budget.status(),
            b68_runtime=self.store.runtime("B68"),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "AUTONOMOUS_INCIDENT_RESPONSE_HISTORY",
            success=True,
            incidents=self.store.list_records("B69", limit=limit),
            history=self.store.history(stage="B69", limit=limit),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B69", {
            **dict(updates),
            "auto_approve": False,
        })
        return self._response(
            "AUTONOMOUS_INCIDENT_RESPONSE_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def start_if_enabled(self) -> dict[str, Any]:
        if bool(self.store.policy("B69").get("enabled", False)):
            return self.start_background()
        return self._response(
            "AUTONOMOUS_INCIDENT_MONITOR_DISABLED",
            success=True,
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        self.store.update_runtime("B69", {
            "running": True,
            "phase": "MONITORING",
        })
        try:
            while not self._stop_event.is_set():
                runtime = self.store.runtime("B69")
                if not bool(runtime.get("paused", False)):
                    self.scan()
                interval = float(
                    self.store.policy("B69").get("interval_seconds", 60.0)
                )
                self._stop_event.wait(max(30.0, interval))
        finally:
            self.store.update_runtime("B69", {
                "running": False,
                "phase": "STOPPED" if self._stop_event.is_set() else "READY",
            })

    def _detect_signals(self, policy: dict[str, Any]) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        b64 = self.store.runtime("B64")
        b64_policy = self.store.policy("B64")
        b68 = self.store.runtime("B68")
        active_leases = int(b64.get("active_leases", 0) or 0)
        max_leases = int(b64_policy.get("max_active_leases", 1) or 1)

        if active_leases > max_leases:
            signals.append(self._signal(
                "RESOURCE_LEASE_OVERFLOW",
                "B64",
                "CRITICAL",
                f"Aktywne dzierżawy {active_leases} przekraczają limit {max_leases}.",
                {"active_leases": active_leases, "limit": max_leases},
            ))
        if str(b64.get("phase", "")).upper() == "LEASED" and active_leases == 0:
            signals.append(self._signal(
                "RESOURCE_RUNTIME_MISMATCH",
                "B64",
                "HIGH",
                "B64 ma fazę LEASED bez aktywnej dzierżawy.",
                {"phase": b64.get("phase"), "active_leases": active_leases},
            ))
        if active_leases > 0 and not bool(b68.get("running", False)):
            signals.append(self._signal(
                "ORPHANED_B68_LEASE",
                "B64",
                "CRITICAL",
                "Istnieje aktywna dzierżawa B68 bez działającego nadzorcy.",
                {"active_leases": active_leases, "b68_phase": b68.get("phase")},
            ))

        b68_phase = str(b68.get("phase", "")).upper()
        if b68_phase in _TERMINAL_B68_PHASES:
            signals.append(self._signal(
                f"B68_{b68_phase}",
                "B68",
                "CRITICAL",
                f"B68 wszedł w fazę {b68_phase}.",
                {"phase": b68_phase, "error": b68.get("last_error", "")},
            ))
        if b68_phase == "STOPPED_PENDING_WORKER" and not bool(
            b68.get("running", False)
        ):
            signals.append(self._signal(
                "B68_PENDING_WORKER_STALE",
                "B68",
                "HIGH",
                "B68 pozostał w STOPPED_PENDING_WORKER bez aktywnego nadzorcy.",
                {"phase": b68_phase},
            ))
        if bool(b68.get("running", False)) and self._is_stale(
            str(b68.get("updated_at", "")),
            float(policy.get("stale_heartbeat_seconds", 900.0)),
        ):
            signals.append(self._signal(
                "B68_HEARTBEAT_STALE",
                "B68",
                "CRITICAL",
                "Nadzorca B68 nie aktualizuje stanu w dopuszczalnym czasie.",
                {"updated_at": b68.get("updated_at", "")},
            ))

        failure_limit = int(policy.get("stage_failure_threshold", 2) or 2)
        for stage in ("B62", "B63", "B64", "B65", "B66", "B67", "B68"):
            runtime = self.store.runtime(stage)
            failures = int(runtime.get("consecutive_failures", 0) or 0)
            error = str(runtime.get("last_error", "")).strip()
            if failures >= failure_limit:
                signals.append(self._signal(
                    "STAGE_FAILURE_THRESHOLD",
                    stage,
                    "HIGH",
                    f"{stage} ma {failures} kolejnych błędów.",
                    {"failures": failures, "error": error},
                ))
        return self._deduplicate_signals(signals)

    def _upsert_incident(
        self,
        signal: dict[str, Any],
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        records = self._chronological_incidents()
        fingerprint = str(signal["fingerprint"])
        window = float(policy.get("dedup_window_seconds", 3600.0))
        now = self._now()
        for item in reversed(records):
            if str(item.get("fingerprint", "")) != fingerprint:
                continue
            if str(item.get("status", "")).upper() not in _OPEN_STATUSES:
                continue
            if self._age_seconds(str(item.get("last_seen_at", ""))) > window:
                break
            item["last_seen_at"] = now
            item["occurrences"] = int(item.get("occurrences", 1) or 1) + 1
            item["evidence"] = dict(signal.get("evidence", {}))
            item["summary"] = str(signal.get("summary", ""))
            if _SEVERITY_ORDER.get(str(signal.get("severity", "LOW")), 1) > _SEVERITY_ORDER.get(str(item.get("severity", "LOW")), 1):
                item["severity"] = str(signal.get("severity", "LOW"))
            self.store.replace_records("B69", records)
            return dict(item)

        incident = {
            "incident_id": f"incident-{uuid4().hex}",
            "fingerprint": fingerprint,
            "status": "OPEN",
            "category": str(signal.get("category", "UNKNOWN")),
            "stage_name": str(signal.get("stage_name", "UNKNOWN")),
            "severity": str(signal.get("severity", "LOW")),
            "summary": str(signal.get("summary", "")),
            "evidence": dict(signal.get("evidence", {})),
            "occurrences": 1,
            "first_seen_at": now,
            "last_seen_at": now,
            "created_at": now,
        }
        return self.store.append_record("B69", incident)

    def _contain(self, incident: dict[str, Any]) -> dict[str, Any]:
        incident_id = str(incident.get("incident_id", ""))
        actions: list[dict[str, Any]] = []
        try:
            stop = self.full_autonomy.stop_background()
            actions.append({
                "action": "STOP_B68",
                "status": str(stop.get("status", "UNKNOWN")),
                "success": bool(stop.get("success", False)),
            })
        except Exception as error:
            self.store.update_policy("B68", {
                "enabled": False,
                "auto_approve": False,
            })
            self.store.update_runtime("B68", {
                "enabled": False,
                "running": False,
                "phase": "STOPPED",
                "last_decision": "STOP",
                "last_error": str(error),
            })
            actions.append({
                "action": "STOP_B68_FALLBACK",
                "status": "FALLBACK",
                "success": True,
                "error": str(error),
            })

        recovery = self.resource_budget.release_owner_leases(
            "B68",
            success=False,
            reason=f"B69_INCIDENT_CONTAINMENT:{incident_id}",
        )
        actions.append({
            "action": "RECOVER_B68_LEASES",
            "status": str(recovery.get("status", "UNKNOWN")),
            "success": bool(recovery.get("success", False)),
            "released_count": int(recovery.get("released_count", 0) or 0),
        })

        records = self._chronological_incidents()
        updated = dict(incident)
        for item in records:
            if str(item.get("incident_id", "")) != incident_id:
                continue
            item["status"] = "CONTAINED"
            item["contained_at"] = self._now()
            item["containment_actions"] = actions
            item["auto_approve"] = False
            updated = dict(item)
            break
        self.store.replace_records("B69", records)
        self.store.record_history("B69", {
            "status": "AUTONOMOUS_INCIDENT_CONTAINED",
            "success": True,
            "phase": "CONTAINED",
            "decision": "CONTAIN",
            "reason": str(updated.get("category", "")),
            "error": "",
            "metadata": {"incident_id": incident_id, "actions": actions},
        })
        return updated

    def _resolve_recovered(
        self,
        active_fingerprints: set[str],
        policy: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not bool(policy.get("auto_resolve_recovered", True)):
            return []
        records = self._chronological_incidents()
        resolved: list[dict[str, Any]] = []
        for item in records:
            if str(item.get("status", "")).upper() not in _OPEN_STATUSES:
                continue
            if str(item.get("fingerprint", "")) in active_fingerprints:
                continue
            item["status"] = "RESOLVED"
            item["resolved_at"] = self._now()
            item["resolution"] = "SIGNAL_RECOVERED"
            resolved.append(dict(item))
        if resolved:
            self.store.replace_records("B69", records)
        return resolved

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime("B69")
        failures = 0 if success else int(runtime.get("consecutive_failures", 0)) + 1
        runtime = self.store.update_runtime("B69", {
            "enabled": bool(self.store.policy("B69").get("enabled", False)),
            "running": self.is_running(),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "consecutive_failures": failures,
            "last_cycle_at": self._now(),
            "last_status": status,
            "last_decision": decision,
            "last_result": {
                "status": status,
                "success": success,
                "detected": int(extra.get("detected", 0) or 0),
            },
            "last_error": "" if success else str(extra.get("error", "")),
        })
        self.store.record_history("B69", {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "reason": f"Wykryte incydenty: {int(extra.get('detected', 0) or 0)}",
            "error": "" if success else str(extra.get("error", "")),
        })
        return self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            **extra,
        )

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "autonomy_governance_suite",
            "stage": "B69",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B69"))),
            "policy": dict(extra.pop("policy", self.store.policy("B69"))),
            "summary": self.store.summary("B69"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    def _reconcile_runtime_after_restart(self) -> None:
        runtime = self.store.runtime("B69")
        if bool(runtime.get("running", False)):
            self.store.update_runtime("B69", {
                "running": False,
                "phase": "RECOVERED_AFTER_RESTART",
                "last_status": "AUTONOMOUS_INCIDENT_MONITOR_RESTART_RECOVERED",
                "last_decision": "RECOVER",
            })

    def _latest_open_incident(self) -> dict[str, Any] | None:
        for item in self.store.list_records("B69", limit=1000):
            if str(item.get("status", "")).upper() in _OPEN_STATUSES:
                return dict(item)
        return None

    def _chronological_incidents(self) -> list[dict[str, Any]]:
        return list(reversed(self.store.list_records("B69", limit=10000)))

    @staticmethod
    def _signal(
        category: str,
        stage: str,
        severity: str,
        summary: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        raw = f"{category}|{stage}".encode("utf-8")
        return {
            "fingerprint": sha256(raw).hexdigest()[:24],
            "category": category,
            "stage_name": stage,
            "severity": severity,
            "summary": summary,
            "evidence": dict(evidence),
        }

    @staticmethod
    def _deduplicate_signals(
        values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in values:
            fingerprint = str(item.get("fingerprint", ""))
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            result.append(item)
        return result

    @staticmethod
    def _incident_counts(values: list[dict[str, Any]]) -> dict[str, int]:
        counts = {
            "open": 0,
            "contained": 0,
            "resolved": 0,
            "critical": 0,
            "high": 0,
        }
        for item in values:
            status = str(item.get("status", "")).upper()
            severity = str(item.get("severity", "")).upper()
            if status == "OPEN":
                counts["open"] += 1
            elif status == "CONTAINED":
                counts["contained"] += 1
            elif status == "RESOLVED":
                counts["resolved"] += 1
            if severity == "CRITICAL":
                counts["critical"] += 1
            elif severity == "HIGH":
                counts["high"] += 1
        return counts

    @staticmethod
    def _should_auto_contain(
        incident: dict[str, Any],
        policy: dict[str, Any],
    ) -> bool:
        return (
            bool(policy.get("auto_contain_critical", True))
            and str(incident.get("severity", "")).upper() == "CRITICAL"
            and str(incident.get("status", "")).upper() == "OPEN"
        )

    @classmethod
    def _is_stale(cls, value: str, threshold: float) -> bool:
        return cls._age_seconds(value) > max(60.0, threshold)

    @staticmethod
    def _age_seconds(value: str) -> float:
        text = str(value).strip()
        if not text:
            return 0.0
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - moment).total_seconds())
        except ValueError:
            return 0.0

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

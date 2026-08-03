from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore


class ResourceBudgetService:
    """B64 central resource guard and persistent daily autonomy budget."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        metric_provider: Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.metric_provider = metric_provider

    def snapshot(self) -> dict[str, Any]:
        if callable(self.metric_provider):
            metrics = dict(self.metric_provider() or {})
        else:
            metrics = self._system_metrics()
        return {
            "cpu_percent": max(0.0, float(metrics.get("cpu_percent", 0.0) or 0.0)),
            "ram_percent": max(0.0, float(metrics.get("ram_percent", 0.0) or 0.0)),
            "free_disk_gb": max(0.0, float(metrics.get("free_disk_gb", 0.0) or 0.0)),
            "captured_at": self._now(),
        }

    def acquire(self, owner: str = "B68") -> dict[str, Any]:
        policy = self.store.policy("B64")
        runtime = self._roll_day(self.store.runtime("B64"))
        runtime = self._sync_active_runtime(runtime)
        metrics = self.snapshot()
        reasons: list[str] = []
        if not bool(policy.get("enabled", True)):
            reasons.append("B64_DISABLED")
        if metrics["cpu_percent"] > float(policy.get("max_cpu_percent", 85.0)):
            reasons.append("CPU_LIMIT")
        if metrics["ram_percent"] > float(policy.get("max_ram_percent", 90.0)):
            reasons.append("RAM_LIMIT")
        if metrics["free_disk_gb"] < float(policy.get("min_free_disk_gb", 2.0)):
            reasons.append("DISK_LIMIT")
        if int(runtime.get("active_leases", 0)) >= int(
            policy.get("max_active_leases", 1)
        ):
            reasons.append("ACTIVE_LEASE_LIMIT")
        if int(runtime.get("cycles_used_today", 0)) >= int(
            policy.get("daily_cycle_budget", 24)
        ):
            reasons.append("DAILY_BUDGET_EXHAUSTED")
        if int(runtime.get("consecutive_failures", 0)) >= int(
            policy.get("max_consecutive_failures", 3)
        ):
            reasons.append("FAILURE_CIRCUIT_OPEN")

        if reasons:
            result = self._response(
                "RESOURCE_BUDGET_DEFERRED",
                success=True,
                allowed=False,
                reasons=reasons,
                metrics=metrics,
                decision="DEFER",
            )
            self._record(result)
            return result

        lease_id = f"resource-lease-{uuid4().hex}"
        lease = self.store.append_record("B64", {
            "lease_id": lease_id,
            "owner": str(owner),
            "status": "ACTIVE",
            "metrics": metrics,
            "created_at": self._now(),
        })
        runtime = self.store.update_runtime("B64", {
            "enabled": True,
            "phase": "LEASED",
            "active_leases": int(runtime.get("active_leases", 0)) + 1,
            "cycles_used_today": int(runtime.get("cycles_used_today", 0)) + 1,
            "last_record_id": lease_id,
            "last_status": "RESOURCE_BUDGET_LEASE_GRANTED",
            "last_decision": "ALLOW",
            "last_error": "",
        })
        result = self._response(
            "RESOURCE_BUDGET_LEASE_GRANTED",
            success=True,
            allowed=True,
            lease=lease,
            metrics=metrics,
            runtime=runtime,
            decision="ALLOW",
        )
        self._record(result)
        return result

    def release(
        self,
        lease_id: str,
        *,
        success: bool = True,
        reason: str = "",
    ) -> dict[str, Any]:
        target = str(lease_id).strip()
        records = self._chronological_records()
        changed: dict[str, Any] | None = None
        for item in records:
            if str(item.get("lease_id", "")) != target:
                continue
            changed = item
            break
        if changed is None:
            runtime = self._sync_active_runtime(self.store.runtime("B64"))
            return self._response(
                "RESOURCE_BUDGET_LEASE_NOT_FOUND",
                success=False,
                allowed=False,
                runtime=runtime,
                errors=["Nie znaleziono dzierżawy B64."],
            )
        if str(changed.get("status", "")).upper() != "ACTIVE":
            runtime = self._sync_active_runtime(self.store.runtime("B64"))
            return self._response(
                "RESOURCE_BUDGET_LEASE_ALREADY_CLOSED",
                success=True,
                allowed=True,
                runtime=runtime,
                lease=changed,
            )
        changed["status"] = "RELEASED" if success else "FAILED"
        changed["released_at"] = self._now()
        changed["reason"] = str(reason)
        self.store.replace_records("B64", records)
        runtime = self.store.runtime("B64")
        failures = 0 if success else int(runtime.get("consecutive_failures", 0)) + 1
        remaining = self._active_count(records)
        runtime = self.store.update_runtime("B64", {
            "phase": "LEASED" if remaining else ("READY" if success else "FAILED"),
            "active_leases": remaining,
            "consecutive_failures": failures,
            "last_status": "RESOURCE_BUDGET_LEASE_RELEASED",
            "last_decision": "RELEASE",
            "last_error": "" if success else str(reason),
        })
        result = self._response(
            "RESOURCE_BUDGET_LEASE_RELEASED",
            success=True,
            allowed=True,
            lease=changed,
            runtime=runtime,
        )
        self._record(result)
        return result

    def release_owner_leases(
        self,
        owner: str,
        *,
        success: bool = True,
        reason: str = "",
    ) -> dict[str, Any]:
        """Close every active lease owned by one supervisor.

        Used only for crash/stop recovery. It never changes global auto-approve
        and it recomputes the runtime counter from persisted lease records.
        """
        target_owner = str(owner).strip()
        records = self._chronological_records()
        released_ids: list[str] = []
        now = self._now()
        for item in records:
            if str(item.get("owner", "")) != target_owner:
                continue
            if str(item.get("status", "")).upper() != "ACTIVE":
                continue
            item["status"] = "RELEASED" if success else "FAILED"
            item["released_at"] = now
            item["reason"] = str(reason)
            released_ids.append(str(item.get("lease_id", "")))
        if released_ids:
            self.store.replace_records("B64", records)
        remaining = self._active_count(records)
        runtime = self.store.runtime("B64")
        failures = int(runtime.get("consecutive_failures", 0))
        if released_ids and not success:
            failures += 1
        runtime = self.store.update_runtime("B64", {
            "phase": "LEASED" if remaining else ("READY" if success else "FAILED"),
            "active_leases": remaining,
            "consecutive_failures": failures,
            "last_status": (
                "RESOURCE_BUDGET_OWNER_LEASES_RELEASED"
                if released_ids else "RESOURCE_BUDGET_OWNER_LEASES_NONE"
            ),
            "last_decision": "RECOVER",
            "last_error": "" if success else str(reason),
        })
        result = self._response(
            "RESOURCE_BUDGET_OWNER_LEASES_RELEASED"
            if released_ids else "RESOURCE_BUDGET_OWNER_LEASES_NONE",
            success=True,
            allowed=True,
            runtime=runtime,
            owner=target_owner,
            released_ids=released_ids,
            released_count=len(released_ids),
            reason=str(reason),
        )
        self._record(result)
        return result

    def reset_failure_circuit(self) -> dict[str, Any]:
        runtime = self.store.update_runtime("B64", {
            "consecutive_failures": 0,
            "phase": "READY",
            "last_error": "",
        })
        return self._response(
            "RESOURCE_BUDGET_CIRCUIT_RESET",
            success=True,
            runtime=runtime,
        )

    def status(self) -> dict[str, Any]:
        runtime = self._roll_day(self.store.runtime("B64"))
        runtime = self._sync_active_runtime(runtime)
        return self._response(
            "RESOURCE_BUDGET_STATUS",
            success=True,
            metrics=self.snapshot(),
            runtime=runtime,
            leases=self.store.list_records("B64", limit=10),
        )

    def update_policy(self, updates: dict[str, Any]) -> dict[str, Any]:
        policy = self.store.update_policy("B64", {
            **dict(updates),
            "max_active_leases": 1,
            "auto_approve": False,
        })
        return self._response(
            "RESOURCE_BUDGET_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def _sync_active_runtime(self, runtime: dict[str, Any]) -> dict[str, Any]:
        records = self._chronological_records()
        active = self._active_count(records)
        phase = str(runtime.get("phase", "IDLE"))
        expected_phase = "LEASED" if active else (
            "READY" if phase == "LEASED" else phase
        )
        if (
            int(runtime.get("active_leases", 0)) == active
            and phase == expected_phase
        ):
            return runtime
        return self.store.update_runtime("B64", {
            "active_leases": active,
            "phase": expected_phase,
            "last_status": "RESOURCE_BUDGET_RUNTIME_RECONCILED",
            "last_decision": "RECOVER",
        })

    def _chronological_records(self) -> list[dict[str, Any]]:
        return list(reversed(self.store.list_records("B64", limit=2000)))

    @staticmethod
    def _active_count(records: list[dict[str, Any]]) -> int:
        return sum(
            1 for item in records
            if str(item.get("status", "")).upper() == "ACTIVE"
        )

    def _roll_day(self, runtime: dict[str, Any]) -> dict[str, Any]:
        today = datetime.now(timezone.utc).date().isoformat()
        if str(runtime.get("budget_date", "")) == today:
            return runtime
        return self.store.update_runtime("B64", {
            "budget_date": today,
            "cycles_used_today": 0,
            "active_leases": 0,
            "consecutive_failures": 0,
            "phase": "READY",
        })

    def _system_metrics(self) -> dict[str, float]:
        cpu = 0.0
        ram = 0.0
        try:
            import psutil  # type: ignore

            cpu = float(psutil.cpu_percent(interval=None))
            ram = float(psutil.virtual_memory().percent)
        except Exception:
            try:
                load = os.getloadavg()[0]
                cpu_count = max(1, os.cpu_count() or 1)
                cpu = min(100.0, max(0.0, load / cpu_count * 100.0))
            except Exception:
                cpu = 0.0
        usage = shutil.disk_usage(self.project_root)
        return {
            "cpu_percent": cpu,
            "ram_percent": ram,
            "free_disk_gb": usage.free / (1024 ** 3),
        }

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
            "stage": "B64",
            "runtime": dict(extra.pop("runtime", self.store.runtime("B64"))),
            "policy": dict(extra.pop("policy", self.store.policy("B64"))),
            "summary": self.store.summary("B64"),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    def _record(self, response: dict[str, Any]) -> None:
        self.store.record_history("B64", {
            "status": response.get("status", "UNKNOWN"),
            "success": bool(response.get("success", False)),
            "phase": response.get("runtime", {}).get("phase", ""),
            "decision": response.get("decision", ""),
            "reason": ", ".join(response.get("reasons", [])[:5]),
            "error": "; ".join(response.get("errors", [])[:5]),
        })

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

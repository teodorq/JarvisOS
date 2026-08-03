from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import BackgroundAutonomyStage, count_statuses, now


class ProductionAutonomy24x7Service(BackgroundAutonomyStage):
    """B79 production coordinator without autonomous approvals."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        services: dict[str, Any] | None = None,
    ) -> None:
        self.services: dict[str, Any] = dict(services or {})
        super().__init__(
            project_root,
            store=store,
            stage="B79",
            thread_name="jarvis-b79-production-autonomy",
            default_interval=300.0,
        )

    def bind_services(self, services: dict[str, Any]) -> None:
        self.services.update(dict(services))

    def start_if_enabled(self) -> dict[str, Any]:
        policy = self.store.policy("B79")
        if (
            bool(policy.get("enabled", False))
            and bool(policy.get("resume_after_restart", True))
        ):
            return self.start_background()
        return self._response(
            "B79_SUPERVISOR_DISABLED",
            success=True,
            decision="HOLD",
        )

    def run_cycle(self) -> dict[str, Any]:
        steps = (
            ("B69", "scan"),
            ("B70", "run_cycle"),
            ("B72", "run_cycle"),
            ("B74", "run_cycle"),
            ("B77", "capture"),
        )
        results: list[dict[str, Any]] = []
        for stage, method in steps:
            service = self.services.get(stage)
            action = getattr(service, method, None)
            if not callable(action):
                results.append({
                    "stage": stage,
                    "status": "SERVICE_UNAVAILABLE",
                    "success": False,
                })
                continue
            try:
                value = action()
                results.append({
                    "stage": stage,
                    "status": str(
                        value.get("status", "UNKNOWN")
                        if isinstance(value, dict) else "UNKNOWN"
                    ),
                    "success": bool(
                        value.get("success", False)
                        if isinstance(value, dict) else False
                    ),
                })
            except Exception as exc:
                results.append({
                    "stage": stage,
                    "status": "CYCLE_STEP_FAILED",
                    "success": False,
                    "error": str(exc),
                })

        success = all(bool(item.get("success", False)) for item in results)
        cycle = self.store.append_record("B79", {
            "cycle_id": f"production-cycle-{uuid4().hex}",
            "status": "COMPLETED" if success else "DEGRADED",
            "results": results,
            "active_leases": int(
                self.store.runtime("B64").get("active_leases", 0) or 0
            ),
            "open_incidents": sum(
                1 for item in self.store.list_records("B69", limit=10000)
                if str(item.get("status", "")).upper() == "OPEN"
            ),
            "pending_recovery_plans": sum(
                1 for item in self.store.list_records("B70", limit=10000)
                if str(item.get("status", "")).upper() == "PREVIEW_READY"
            ),
            "auto_approve": False,
            "created_at": now(),
        })
        return self._finish(
            "PRODUCTION_AUTONOMY_CYCLE_COMPLETED"
            if success else "PRODUCTION_AUTONOMY_CYCLE_DEGRADED",
            success=success,
            phase="READY" if success else "DEGRADED",
            decision="CONTINUE" if success else "HOLD",
            record=cycle,
            error="" if success else "Jeden lub więcej kroków B79 nie powiodło się.",
            cycle=cycle,
            results=results,
        )

    def daily_report(self) -> dict[str, Any]:
        cycles = self.store.list_records("B79", limit=100)
        report = {
            "generated_at": now(),
            "cycles": len(cycles),
            "completed": sum(
                1 for item in cycles
                if str(item.get("status", "")).upper() == "COMPLETED"
            ),
            "degraded": sum(
                1 for item in cycles
                if str(item.get("status", "")).upper() == "DEGRADED"
            ),
            "open_incidents": sum(
                1 for item in self.store.list_records("B69", limit=10000)
                if str(item.get("status", "")).upper() == "OPEN"
            ),
            "active_leases": int(
                self.store.runtime("B64").get("active_leases", 0) or 0
            ),
            "auto_approve": False,
        }
        return self._response(
            "PRODUCTION_AUTONOMY_DAILY_REPORT",
            success=True,
            decision="REPORT",
            daily_report=report,
        )

    def status(self) -> dict[str, Any]:
        cycles = self.store.list_records("B79", limit=50)
        return self._response(
            "PRODUCTION_AUTONOMY_24X7_STATUS",
            success=True,
            cycles=cycles,
            cycle_counts=count_statuses(cycles),
            safety={
                "auto_approve": False,
                "max_active_leases": int(
                    self.store.policy("B64").get("max_active_leases", 1)
                ),
                "automatic_code_execution": False,
            },
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "PRODUCTION_AUTONOMY_24X7_HISTORY",
            success=True,
            cycles=self.store.list_records("B79", limit=limit),
            history=self.store.history(stage="B79", limit=limit),
        )

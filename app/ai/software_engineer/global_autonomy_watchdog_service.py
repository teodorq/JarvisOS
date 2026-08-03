from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import BackgroundAutonomyStage, count_statuses, now


_WATCHED_STAGES = ("B68", "B69", "B70", "B72", "B79")


class GlobalAutonomyWatchdogService(BackgroundAutonomyStage):
    """B74 heartbeat checks and bounded restart reconciliation."""

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
            stage="B74",
            thread_name="jarvis-b74-global-watchdog",
            default_interval=60.0,
        )

    def bind_services(self, services: dict[str, Any]) -> None:
        self.services.update(dict(services))

    def run_cycle(self) -> dict[str, Any]:
        policy = self.store.policy("B74")
        threshold = float(policy.get("stale_heartbeat_seconds", 900.0))
        events: list[dict[str, Any]] = []
        for stage in _WATCHED_STAGES:
            runtime = self.store.runtime(stage)
            if not bool(runtime.get("running", False)):
                continue
            heartbeat = str(
                runtime.get("last_cycle_at")
                or runtime.get("updated_at")
                or ""
            )
            stale = self._age_seconds(heartbeat) > threshold
            service = self.services.get(stage)
            is_running = getattr(service, "is_running", None)
            thread_alive = bool(is_running()) if callable(is_running) else True
            if not thread_alive:
                events.append(self._reconcile(stage, "WORKER_NOT_ALIVE"))
            elif stale:
                events.append(self._handle_stale(stage, service, policy))

        status = "GLOBAL_WATCHDOG_CLEAR" if not events else "GLOBAL_WATCHDOG_EVENTS"
        phase = "READY" if not events else "DEGRADED"
        decision = "CLEAR" if not events else "RECONCILE"
        for event in events:
            self.store.append_record("B74", event)
        return self._finish(
            status,
            success=True,
            phase=phase,
            decision=decision,
            record=events[-1] if events else None,
            events=events,
            event_counts=count_statuses(events),
        )

    def status(self) -> dict[str, Any]:
        events = self.store.list_records("B74", limit=50)
        return self._response(
            "GLOBAL_AUTONOMY_WATCHDOG_STATUS",
            success=True,
            events=events,
            event_counts=count_statuses(events),
            watched_stages=list(_WATCHED_STAGES),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "GLOBAL_AUTONOMY_WATCHDOG_HISTORY",
            success=True,
            events=self.store.list_records("B74", limit=limit),
            history=self.store.history(stage="B74", limit=limit),
        )

    def _handle_stale(
        self,
        stage: str,
        service: Any,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        if not bool(policy.get("auto_restart_safe", False)):
            return self._event(stage, "STALE_HEARTBEAT", "OBSERVED")
        restart = getattr(service, "stop_background", None)
        start = getattr(service, "start_background", None)
        if not callable(restart) or not callable(start):
            return self._event(stage, "STALE_HEARTBEAT", "UNAVAILABLE")
        stopped = restart()
        started = start()
        success = bool(stopped.get("success")) and bool(started.get("success"))
        return self._event(
            stage,
            "STALE_HEARTBEAT",
            "RESTARTED" if success else "RESTART_FAILED",
            success=success,
        )

    def _reconcile(self, stage: str, category: str) -> dict[str, Any]:
        self.store.update_runtime(stage, {
            "running": False,
            "phase": "RECOVERED_AFTER_WATCHDOG",
            "last_status": f"{stage}_WATCHDOG_RECONCILED",
            "last_decision": "HOLD",
            "last_error": "",
        })
        return self._event(stage, category, "RECONCILED")

    @staticmethod
    def _event(
        stage: str,
        category: str,
        action: str,
        *,
        success: bool = True,
    ) -> dict[str, Any]:
        return {
            "event_id": f"watchdog-{uuid4().hex}",
            "status": "RESOLVED" if success else "FAILED",
            "stage_name": stage,
            "category": category,
            "action": action,
            "success": success,
            "created_at": now(),
        }

    @staticmethod
    def _age_seconds(value: str) -> float:
        if not value:
            return 10**12
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return max(
                0.0,
                (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc))
                .total_seconds(),
            )
        except (TypeError, ValueError):
            return 10**12

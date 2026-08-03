from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any

from .autonomy_governance_store import AutonomyGovernanceStore


class BackgroundAutonomyStage:
    """Shared bounded lifecycle for optional B7x background supervisors."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        stage: str,
        thread_name: str,
        default_interval: float,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.stage = str(stage).upper()
        self.thread_name = thread_name
        self.default_interval = max(1.0, float(default_interval))
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._reconcile_runtime_after_restart()

    def run_cycle(self) -> dict[str, Any]:
        raise NotImplementedError

    def start_background(self) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return self._response(
                    f"{self.stage}_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                    decision="MONITOR",
                )
            self._stop_event.clear()
            self.store.update_policy(self.stage, {
                "enabled": True,
                "auto_approve": False,
            })
            runtime = self.store.update_runtime(self.stage, {
                "enabled": True,
                "running": True,
                "paused": False,
                "phase": "STARTING",
                "last_status": f"{self.stage}_SUPERVISOR_STARTED",
                "last_decision": "MONITOR",
                "last_error": "",
            })
            self._thread = threading.Thread(
                target=self._run_loop,
                name=self.thread_name,
                daemon=True,
            )
            self._thread.start()
        return self._response(
            f"{self.stage}_SUPERVISOR_STARTED",
            success=True,
            runtime=runtime,
            decision="MONITOR",
        )

    def stop_background(self) -> dict[str, Any]:
        with self._lock:
            self._stop_event.set()
            worker = self._thread
        if worker is not None and worker.is_alive():
            worker.join(timeout=10.0)
        alive = bool(worker is not None and worker.is_alive())
        with self._lock:
            if worker is not None and not alive:
                self._thread = None
            self.store.update_policy(self.stage, {
                "enabled": False,
                "auto_approve": False,
            })
            runtime = self.store.update_runtime(self.stage, {
                "enabled": False,
                "running": alive,
                "paused": False,
                "phase": "STOPPED_PENDING_WORKER" if alive else "STOPPED",
                "last_status": (
                    f"{self.stage}_SUPERVISOR_STOPPED_PENDING_WORKER"
                    if alive else f"{self.stage}_SUPERVISOR_STOPPED"
                ),
                "last_decision": "STOP",
                "last_error": "",
            })
        return self._response(
            str(runtime.get("last_status", f"{self.stage}_SUPERVISOR_STOPPED")),
            success=True,
            runtime=runtime,
            worker_alive=alive,
            decision="STOP",
        )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime(self.stage, {
            "paused": True,
            "phase": "PAUSED",
            "last_status": f"{self.stage}_SUPERVISOR_PAUSED",
            "last_decision": "PAUSE",
        })
        return self._response(
            f"{self.stage}_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
            decision="PAUSE",
        )

    def resume(self) -> dict[str, Any]:
        self.store.update_policy(self.stage, {
            "enabled": True,
            "auto_approve": False,
        })
        runtime = self.store.update_runtime(self.stage, {
            "enabled": True,
            "paused": False,
            "phase": "RESUMING",
            "last_status": f"{self.stage}_SUPERVISOR_RESUMING",
            "last_decision": "MONITOR",
        })
        if not self.is_running():
            return self.start_background()
        return self._response(
            f"{self.stage}_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
            decision="MONITOR",
        )

    def start_if_enabled(self) -> dict[str, Any]:
        if bool(self.store.policy(self.stage).get("enabled", False)):
            return self.start_background()
        return self._response(
            f"{self.stage}_SUPERVISOR_DISABLED",
            success=True,
            decision="HOLD",
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        self.store.update_runtime(self.stage, {
            "running": True,
            "phase": "MONITORING",
        })
        try:
            while not self._stop_event.is_set():
                runtime = self.store.runtime(self.stage)
                if not bool(runtime.get("paused", False)):
                    self.run_cycle()
                interval = float(
                    self.store.policy(self.stage).get(
                        "interval_seconds",
                        self.default_interval,
                    )
                )
                self._stop_event.wait(max(1.0, interval))
        finally:
            self.store.update_runtime(self.stage, {
                "running": False,
                "phase": "STOPPED" if self._stop_event.is_set() else "READY",
            })

    def _finish(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        decision: str,
        record: dict[str, Any] | None = None,
        error: str = "",
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime(self.stage)
        failures = 0 if success else int(
            runtime.get("consecutive_failures", 0) or 0
        ) + 1
        runtime = self.store.update_runtime(self.stage, {
            "enabled": bool(self.store.policy(self.stage).get("enabled", False)),
            "running": self.is_running(),
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0) or 0) + 1,
            "consecutive_failures": failures,
            "last_cycle_at": now(),
            "last_status": status,
            "last_decision": decision,
            "last_record_id": record_id(record),
            "last_result": {
                "status": status,
                "success": success,
                "record_id": record_id(record),
            },
            "last_error": "" if success else str(error)[-4000:],
        })
        self.store.record_history(self.stage, {
            "status": status,
            "success": success,
            "phase": phase,
            "decision": decision,
            "reason": str(extra.get("reason", "")),
            "error": "" if success else str(error),
            "metadata": {"record_id": record_id(record)},
        })
        return self._response(
            status,
            success=success,
            runtime=runtime,
            decision=decision,
            record=record,
            errors=[] if success else [str(error)],
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
        runtime = dict(extra.pop("runtime", self.store.runtime(self.stage)))
        if (
            str(runtime.get("phase", "")) == "STOPPED_PENDING_WORKER"
            and not self.is_running()
        ):
            runtime = self.store.update_runtime(self.stage, {
                "running": False,
                "phase": "STOPPED",
                "last_status": f"{self.stage}_SUPERVISOR_STOPPED",
                "last_decision": "STOP",
                "last_error": "",
            })
        return {
            "success": success,
            "status": status,
            "operation": "autonomy_governance_suite",
            "stage": self.stage,
            "runtime": runtime,
            "policy": dict(extra.pop("policy", self.store.policy(self.stage))),
            "summary": self.store.summary(self.stage),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }

    def _reconcile_runtime_after_restart(self) -> None:
        runtime = self.store.runtime(self.stage)
        if bool(runtime.get("running", False)):
            self.store.update_runtime(self.stage, {
                "running": False,
                "phase": "RECOVERED_AFTER_RESTART",
                "last_status": f"{self.stage}_RESTART_RECONCILED",
                "last_decision": "HOLD",
                "last_error": "",
            })


def update_record(
    store: AutonomyGovernanceStore,
    stage: str,
    record: dict[str, Any],
    updates: dict[str, Any],
    *,
    id_fields: tuple[str, ...],
) -> dict[str, Any]:
    values = list(reversed(store.list_records(stage, limit=10000)))
    updated = {**dict(record), **dict(updates)}
    found = False
    for index, item in enumerate(values):
        if all(
            str(item.get(field, "")) == str(record.get(field, ""))
            for field in id_fields
        ):
            values[index] = updated
            found = True
            break
    if not found:
        values.append(updated)
    store.replace_records(stage, values)
    return dict(updated)


def count_statuses(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in records:
        status = str(item.get("status", "UNKNOWN")).upper()
        counts[status.casefold()] = counts.get(status.casefold(), 0) + 1
    return counts


def record_id(record: dict[str, Any] | None) -> str:
    value = dict(record or {})
    for key in (
        "execution_id", "lesson_id", "snapshot_id", "event_id",
        "deployment_id", "train_id", "memory_id", "audit_id", "cycle_id",
        "recovery_id", "incident_id",
    ):
        if value.get(key):
            return str(value[key])
    return ""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()

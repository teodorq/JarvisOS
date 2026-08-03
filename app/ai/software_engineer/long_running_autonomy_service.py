from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import threading
import traceback
from typing import Any, Callable

from .full_autonomy_workflow import FullAutonomyWorkflow
from .autonomous_diagnostics_service import AutonomousDiagnosticsService
from .long_running_autonomy_models import (
    LongRunningJob,
    TERMINAL_JOB_STATES,
)
from .long_running_autonomy_scheduler import (
    LongRunningAutonomyScheduler,
)
from .long_running_autonomy_store import (
    LongRunningAutonomyStore,
)
from .long_running_autonomy_watchdog import (
    LongRunningAutonomyWatchdog,
)
from .long_running_resource_guard import (
    LongRunningResourceGuard,
)


class LongRunningAutonomyService:
    """Persistent supervisor for safe, long-running autonomy jobs."""

    APPROVAL_LEASE_RETRY_SECONDS = 2.0
    APPROVAL_LEASE_MAX_CYCLES = 8

    def __init__(
        self,
        project_root: str | Path,
        *,
        workflow: FullAutonomyWorkflow | Any | None = None,
        store: LongRunningAutonomyStore | None = None,
        scheduler: LongRunningAutonomyScheduler | None = None,
        resource_guard: LongRunningResourceGuard | None = None,
        watchdog: LongRunningAutonomyWatchdog | None = None,
        diagnostics_service: AutonomousDiagnosticsService | Any | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.workflow = workflow or FullAutonomyWorkflow(self.project_root)
        self.store = store or LongRunningAutonomyStore(self.project_root)
        self.scheduler = scheduler or LongRunningAutonomyScheduler()
        self.resource_guard = resource_guard or LongRunningResourceGuard(
            self.project_root
        )
        self.watchdog = watchdog or LongRunningAutonomyWatchdog()
        self.diagnostics_service = (
            diagnostics_service
            or AutonomousDiagnosticsService(
                self.project_root,
                long_running_store=self.store,
            )
        )
        self.clock = clock or (
            lambda: datetime.now(timezone.utc)
        )
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def enqueue(
        self,
        objective: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = dict(context or {})
        objective = str(objective).strip()
        if not objective:
            return self._error(
                "LONG_RUNNING_OBJECTIVE_REQUIRED",
                ["Podaj cel długotrwałej autonomii."],
            )

        schedule = self.scheduler.normalize(
            values.get("schedule")
            if isinstance(values.get("schedule"), dict)
            else self._schedule_from_context(values),
            now=self.clock(),
        )
        job = LongRunningJob(
            objective=objective,
            priority=self._bounded_int(
                values.get("priority", 50), 0, 100
            ),
            schedule=schedule,
            execution_context=self._safe_execution_context(values),
            resource_policy=(
                dict(values.get("resource_policy", {}))
                if isinstance(values.get("resource_policy"), dict)
                else {}
            ),
            restart_policy=str(
                values.get("restart_policy", "RESUME")
            ).upper(),
            max_attempts=self._bounded_int(
                values.get("max_attempts", 3), 1, 10
            ),
            next_run_at=str(schedule.get("next_run_at", "")),
            metadata=dict(values.get("metadata", {}) or {}),
        )
        job.state = (
            "QUEUED"
            if schedule.get("type") == "immediate"
            else "SCHEDULED"
        )
        saved = self.store.save_job(job)
        self.store.record_event(
            "LONG_RUNNING_JOB_ENQUEUED",
            job_id=job.job_id,
            metadata={
                "schedule_type": schedule.get("type", "immediate"),
            },
        )
        return self._response(
            "LONG_RUNNING_JOB_ENQUEUED",
            job=saved,
            success=True,
        )

    def tick(
        self,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            current = self._utc(now or self.clock())
            runtime = self.store.runtime()
            policy = self.store.policy()
            self.store.update_runtime({
                "running": True,
                "heartbeat_at": current.isoformat(),
                "last_tick_at": current.isoformat(),
            })

            if bool(runtime.get("paused", False)):
                return self._cycle_result(
                    "LONG_RUNNING_SUPERVISOR_PAUSED",
                    [],
                    current,
                )

            recovered = self.recover_interrupted(now=current)
            exhausted = self._fail_exhausted_jobs(now=current)
            jobs = self.store.list_jobs(limit=1000)
            due = self.scheduler.due_jobs(
                jobs,
                now=current,
                limit=min(
                    int(policy.get("max_jobs_per_tick", 1)),
                    int(policy.get("max_parallel_jobs", 1)),
                ),
            )
            processed: list[dict[str, Any]] = list(exhausted)
            for job in due:
                guard = self.resource_guard.evaluate(
                    policy,
                    overrides=dict(job.get("resource_policy", {}) or {}),
                )
                if not guard.get("allowed", False):
                    waiting = dict(job)
                    waiting["state"] = "WAITING_RESOURCES"
                    waiting["last_result"] = guard
                    waiting["last_error"] = "; ".join(
                        str(item)
                        for item in guard.get("reasons", [])
                    )
                    waiting["next_run_at"] = (
                        current + timedelta(
                            seconds=float(
                                policy.get(
                                    "resource_retry_seconds",
                                    60.0,
                                )
                            )
                        )
                    ).isoformat()
                    self.store.save_job(waiting)
                    self.store.record_event(
                        "LONG_RUNNING_JOB_WAITING_RESOURCES",
                        job_id=str(waiting.get("job_id", "")),
                        metadata=guard,
                    )
                    processed.append(waiting)
                    continue

                processed.append(
                    self._execute_job(job, now=current)
                )

            return self._cycle_result(
                (
                    "LONG_RUNNING_TICK_COMPLETED"
                    if processed
                    else "LONG_RUNNING_TICK_IDLE"
                ),
                processed,
                current,
                recovered=len(recovered),
            )

    def start_background(self) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return self._response(
                    "LONG_RUNNING_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                )
            self.store.update_runtime({
                "enabled": True,
                "paused": False,
                "running": True,
                "last_error": "",
            })
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-long-running-autonomy",
                daemon=True,
            )
            self._thread.start()
            self.store.record_event(
                "LONG_RUNNING_SUPERVISOR_STARTED"
            )
            return self._response(
                "LONG_RUNNING_SUPERVISOR_STARTED",
                success=True,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        self.store.compact()
        if bool(self.store.runtime().get("enabled", False)):
            self.recover_interrupted(force=True)
            self._fail_exhausted_jobs(now=self.clock())
            return self.start_background()
        self.recover_interrupted()
        self._fail_exhausted_jobs(now=self.clock())
        return self._response(
            "LONG_RUNNING_SUPERVISOR_DISABLED",
            success=True,
        )

    def stop_background(self) -> dict[str, Any]:
        self._stop_event.set()
        self.store.update_runtime({
            "enabled": False,
            "running": False,
        })
        self.store.record_event(
            "LONG_RUNNING_SUPERVISOR_STOPPED"
        )
        return self._response(
            "LONG_RUNNING_SUPERVISOR_STOPPED",
            success=True,
        )

    def pause_supervisor(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({"paused": True})
        return self._response(
            "LONG_RUNNING_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume_supervisor(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({"paused": False})
        return self._response(
            "LONG_RUNNING_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
        )

    def pause_job(self, job_id: str) -> dict[str, Any]:
        return self._set_job_state(job_id, "PAUSED")

    def resume_job(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if job is None:
            return self._job_not_found(job_id)

        state = str(job.get("state", "")).upper()
        if state in {"COMPLETED", "CANCELLED"}:
            return self._response(
                "LONG_RUNNING_JOB_TERMINAL",
                job=job,
                success=False,
                errors=["Zadanie ma już status końcowy."],
            )

        if state == "FAILED" or self._attempts_exhausted(job):
            metadata = dict(job.get("metadata", {}) or {})
            metadata["manual_restarts"] = int(
                metadata.get("manual_restarts", 0)
            ) + 1
            job.update({
                "attempts": 0,
                "autonomy_run_id": "",
                "started_at": "",
                "last_result": {},
                "metadata": metadata,
            })

        job["state"] = "QUEUED"
        job["next_run_at"] = self._utc(self.clock()).isoformat()
        job["completed_at"] = ""
        job["last_error"] = ""
        saved = self.store.save_job(job)
        self.store.record_event(
            "LONG_RUNNING_JOB_RESUMED",
            job_id=job_id,
        )
        return self._response(
            "LONG_RUNNING_JOB_RESUMED",
            job=saved,
            success=True,
        )

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._set_job_state(job_id, "CANCELLED")

    def run_job_now(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if job is None:
            return self._job_not_found(job_id)
        if str(job.get("state", "")).upper() in TERMINAL_JOB_STATES:
            return self._response(
                "LONG_RUNNING_JOB_TERMINAL",
                job=job,
                success=False,
                errors=["Zadanie ma już status końcowy."],
            )
        job["state"] = "QUEUED"
        job["next_run_at"] = self._utc(self.clock()).isoformat()
        self.store.save_job(job)
        return self.tick(now=self.clock())

    def delete_job(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if job is None:
            return self._job_not_found(job_id)
        state = str(job.get("state", "")).upper()
        if state not in TERMINAL_JOB_STATES:
            return self._response(
                "LONG_RUNNING_JOB_DELETE_BLOCKED",
                job=job,
                success=False,
                errors=[
                    "Można usunąć tylko zadanie zakończone, "
                    "nieudane albo anulowane."
                ],
            )
        removed = self.store.delete_job(job_id)
        if removed is None:
            return self._job_not_found(job_id)
        self.store.record_event(
            "LONG_RUNNING_JOB_DELETED",
            job_id=job_id,
            metadata={"previous_state": state},
        )
        return self._response(
            "LONG_RUNNING_JOB_DELETED",
            job=removed,
            success=True,
            removed=1,
        )

    def clear_terminal_jobs(self) -> dict[str, Any]:
        removed = self.store.delete_jobs_by_state(
            set(TERMINAL_JOB_STATES)
        )
        self.store.record_event(
            "LONG_RUNNING_TERMINAL_JOBS_CLEARED",
            metadata={
                "removed": len(removed),
                "job_ids": [
                    str(item.get("job_id", ""))
                    for item in removed
                ][:100],
            },
        )
        return self._response(
            "LONG_RUNNING_TERMINAL_JOBS_CLEARED",
            success=True,
            removed=len(removed),
            removed_job_ids=[
                str(item.get("job_id", ""))
                for item in removed
            ],
        )

    def status(self, job_id: str = "") -> dict[str, Any]:
        if job_id:
            job = self.store.get_job(job_id)
            if job is None:
                return self._job_not_found(job_id)
            job = self._refresh_job_monitoring(job)
            return self._response(
                "LONG_RUNNING_JOB_STATUS",
                job=job,
                success=True,
            )

        jobs = [
            self._refresh_job_monitoring(job)
            for job in self.store.list_jobs(limit=100)
        ]
        counts: dict[str, int] = {}
        for job in jobs:
            state = str(job.get("state", "UNKNOWN")).upper()
            counts[state] = counts.get(state, 0) + 1
        return self._response(
            "LONG_RUNNING_AUTONOMY_STATUS",
            success=True,
            jobs=jobs,
            runtime={
                **self.store.runtime(),
                "thread_running": self.is_running(),
            },
            policy=self.store.policy(),
            counts=counts,
        )

    def recent(self, *, limit: int = 20) -> dict[str, Any]:
        jobs = [
            self._refresh_job_monitoring(job)
            for job in self.store.list_jobs(limit=limit)
        ]
        counts: dict[str, int] = {}
        for job in jobs:
            state = str(job.get("state", "UNKNOWN")).upper()
            counts[state] = counts.get(state, 0) + 1
        return self._response(
            "LONG_RUNNING_AUTONOMY_RECENT",
            success=True,
            jobs=jobs,
            events=self.store.events(limit=limit),
            counts=counts,
        )

    def update_policy(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        safe = dict(updates)
        safe["auto_approve"] = False
        policy = self.store.update_policy(safe)
        return self._response(
            "LONG_RUNNING_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def recover_interrupted(
        self,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        policy = self.store.policy()
        jobs = self.store.list_jobs(limit=1000)
        if force:
            recovered = []
            for item in jobs:
                if str(item.get("state", "")).upper() != "RUNNING":
                    continue
                job = dict(item)
                if self._attempts_exhausted(job):
                    job["state"] = "FAILED"
                    job["completed_at"] = self._utc(
                        now or self.clock()
                    ).isoformat()
                    job["next_run_at"] = ""
                    job["last_error"] = (
                        "Przekroczono limit prób przed odzyskaniem "
                        "przerwanego zadania."
                    )
                else:
                    job["state"] = (
                        "RECOVERING"
                        if str(
                            job.get("restart_policy", "RESUME")
                        ).upper() == "RESUME"
                        else "FAILED"
                    )
                    job["last_error"] = (
                        "Wykryto przerwany przebieg po ponownym "
                        "uruchomieniu JARVIS OS."
                    )
                recovered.append(job)
        else:
            recovered = self.watchdog.recover(
                jobs,
                stale_after_seconds=float(
                    policy.get("stale_after_seconds", 300.0)
                ),
                now=now or self.clock(),
            )
        for job in recovered:
            if (
                str(job.get("state", "")).upper() == "RECOVERING"
                and self._attempts_exhausted(job)
            ):
                job["state"] = "FAILED"
                job["last_error"] = (
                    "Przekroczono limit prób podczas odzyskiwania "
                    "przerwanego zadania."
                )

            if str(job.get("state", "")).upper() == "RECOVERING":
                job["next_run_at"] = self._utc(
                    now or self.clock()
                ).isoformat()
                event = "LONG_RUNNING_JOB_RECOVERED"
            else:
                job["completed_at"] = self._utc(
                    now or self.clock()
                ).isoformat()
                job["next_run_at"] = ""
                event = (
                    "LONG_RUNNING_JOB_ATTEMPTS_EXHAUSTED"
                    if self._attempts_exhausted(job)
                    else "LONG_RUNNING_JOB_RECOVERY_FAILED"
                )
            self.store.save_job(job)
            self.store.record_event(
                event,
                job_id=str(job.get("job_id", "")),
                metadata={"state": job.get("state")},
            )
        if recovered:
            runtime = self.store.runtime()
            self.store.update_runtime({
                "recovered_jobs": int(
                    runtime.get("recovered_jobs", 0)
                ) + len(recovered)
            })
        return recovered

    def repair_queue(
        self,
        *,
        force_running: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Compact runtime state and release exhausted queue slots."""
        with self._lock:
            current = self._utc(now or self.clock())
            before_bytes = (
                self.store.path.stat().st_size
                if self.store.path.exists()
                else 0
            )
            self.store.compact()
            recovered = self.recover_interrupted(
                now=current,
                force=force_running,
            )
            exhausted = self._fail_exhausted_jobs(now=current)
            if force_running:
                self.store.update_runtime({"running": False})
            self.store.compact()
            repaired_jobs = [
                *[
                    item
                    for item in recovered
                    if str(item.get("state", "")).upper() == "FAILED"
                ],
                *exhausted,
            ]
            after_bytes = (
                self.store.path.stat().st_size
                if self.store.path.exists()
                else 0
            )
            return self._response(
                "LONG_RUNNING_QUEUE_REPAIRED",
                success=True,
                recovered=len(recovered),
                repaired=len(repaired_jobs),
                repaired_job_ids=[
                    str(item.get("job_id", ""))
                    for item in repaired_jobs
                ],
                before_bytes=before_bytes,
                after_bytes=after_bytes,
            )

    def _fail_exhausted_jobs(
        self,
        *,
        now: datetime,
    ) -> list[dict[str, Any]]:
        repaired: list[dict[str, Any]] = []
        for job in self.store.list_jobs(limit=1000):
            state = str(job.get("state", "")).upper()
            if state not in self.scheduler.DUE_STATES:
                continue
            if not self._attempts_exhausted(job):
                continue
            repaired.append(
                self._fail_attempts_exhausted(job, now=now)
            )
        return repaired

    def _fail_attempts_exhausted(
        self,
        job: dict[str, Any],
        *,
        now: datetime,
        last_status: str = "",
    ) -> dict[str, Any]:
        value = dict(job)
        attempts = int(value.get("attempts", 0) or 0)
        max_attempts = max(
            1,
            int(value.get("max_attempts", 3) or 3),
        )
        previous_error = str(value.get("last_error", "")).strip()
        message = (
            f"Przekroczono limit prób ({attempts}/{max_attempts})."
        )
        if previous_error and previous_error not in message:
            message = f"{message} {previous_error}"

        value.update({
            "state": "FAILED",
            "completed_at": now.isoformat(),
            "next_run_at": "",
            "last_error": message[:4000],
        })
        self._finish_approval_lease(
            value,
            state="CONSUMED_ATTEMPTS_EXHAUSTED",
            now=now,
        )
        saved = self.store.save_job(value)
        self.store.record_event(
            "LONG_RUNNING_JOB_ATTEMPTS_EXHAUSTED",
            job_id=str(value.get("job_id", "")),
            metadata={
                "attempts": attempts,
                "max_attempts": max_attempts,
                "last_status": str(last_status),
            },
        )
        return saved

    @staticmethod
    def _attempts_exhausted(
        job: dict[str, Any],
    ) -> bool:
        try:
            attempts = int(job.get("attempts", 0) or 0)
        except (TypeError, ValueError):
            attempts = 0
        try:
            max_attempts = int(job.get("max_attempts", 3) or 3)
        except (TypeError, ValueError):
            max_attempts = 3
        return attempts >= max(1, max_attempts)

    def is_running(self) -> bool:
        thread = self._thread
        return bool(
            thread
            and thread.is_alive()
            and not self._stop_event.is_set()
        )

    def _execute_job(
        self,
        job: dict[str, Any],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        if self._attempts_exhausted(job):
            return self._fail_attempts_exhausted(job, now=now)

        value = self.watchdog.heartbeat(job, now=now)
        value["state"] = "RUNNING"
        value["started_at"] = value.get("started_at") or now.isoformat()
        value["attempts"] = int(value.get("attempts", 0)) + 1
        approval_lease = self._advance_approval_lease(value, now=now)
        value["last_error"] = ""
        value["last_result"] = {
            "success": True,
            "status": "LONG_RUNNING_JOB_EXECUTING",
            "operation": "long_running_autonomy",
            "autonomy_run_id": str(value.get("autonomy_run_id", "")),
            "progress_percent": self._current_progress(value),
            "phase": "EXECUTING_FULL_AUTONOMY",
            "updated_at": now.isoformat(),
            "approval_lease_state": (
                "ACTIVE" if approval_lease else ""
            ),
            "approval_lease_id": str(
                approval_lease.get("lease_id", "")
            ),
        }
        self.store.save_job(value)
        self.store.record_event(
            "LONG_RUNNING_JOB_STARTED",
            job_id=str(value.get("job_id", "")),
            metadata={"attempt": value["attempts"]},
        )

        workflow_error: BaseException | None = None
        traceback_text = ""
        try:
            response = self._run_workflow(value)
        except Exception as error:
            workflow_error = error
            traceback_text = "".join(
                traceback.format_exception(
                    type(error),
                    error,
                    error.__traceback__,
                )
            )
            response = {
                "success": False,
                "status": "LONG_RUNNING_WORKFLOW_EXCEPTION",
                "errors": [f"{type(error).__name__}: {error}"],
                "traceback": traceback_text,
            }

        diagnostic_response = self.diagnostics_service.record_job_result(
            value,
            response,
            exception=workflow_error,
            traceback_text=traceback_text,
        )
        diagnostic = dict(
            diagnostic_response.get("diagnostic", {}) or {}
        )
        response = {
            **dict(response),
            "diagnostic_id": str(
                diagnostic.get("diagnostic_id", "")
            ),
            "diagnostic_category": str(
                diagnostic.get("category", "UNKNOWN")
            ),
            "diagnostic_severity": str(
                diagnostic.get("severity", "WARNING")
            ),
            "repairable": bool(
                diagnostic.get("repairable", False)
            ),
            "requires_approval": bool(
                diagnostic.get("requires_approval", False)
            ),
        }
        value["last_result"] = self.store.compact_result(response)
        self._decorate_result_with_approval_lease(value)
        autonomy_run_id = str(
            response.get(
                "autonomy_run_id",
                value.get("autonomy_run_id", ""),
            )
        ).strip()
        if autonomy_run_id:
            value["autonomy_run_id"] = autonomy_run_id

        status = str(response.get("status", "")).upper()
        if status == "FULL_AUTONOMY_COMPLETED":
            self._finish_approval_lease(
                value,
                state="CONSUMED_COMPLETED",
                now=now,
            )
            return self._complete_job(value, response, now=now)

        if status == "FULL_AUTONOMY_RUNNING":
            value["state"] = "SCHEDULED"
            value["attempts"] = max(0, int(value.get("attempts", 0)) - 1)
            value["next_run_at"] = (
                now + timedelta(seconds=1.0)
            ).isoformat()
            value["last_error"] = ""
            saved = self.store.save_job(value)
            self.store.record_event(
                "LONG_RUNNING_JOB_PROGRESS_CHECKPOINTED",
                job_id=str(value.get("job_id", "")),
            )
            return saved

        if status == "FULL_AUTONOMY_PAUSED":
            if self._is_constraints_pause(response, diagnostic):
                diagnostic = {
                    **diagnostic,
                    "category": "CONSTRAINTS_PAUSE",
                    "severity": "WARNING",
                    "root_cause": (
                        "Żadna kampania nie spełniła aktualnych "
                        "ograniczeń wykonania."
                    ),
                    "retryable": False,
                    "repairable": False,
                    "requires_approval": False,
                }
                return self._defer_constraints_pause(
                    value,
                    response,
                    diagnostic=diagnostic,
                    now=now,
                )
            if bool(diagnostic.get("requires_approval", False)):
                if self._approval_lease_active(value):
                    lease = self._approval_lease(value)
                    cycles = int(lease.get("cycles", 0) or 0)
                    maximum = int(
                        lease.get(
                            "max_cycles",
                            self.APPROVAL_LEASE_MAX_CYCLES,
                        )
                        or self.APPROVAL_LEASE_MAX_CYCLES
                    )
                    if cycles < maximum:
                        value["state"] = "SCHEDULED"
                        # A still-open approval gate is not a failed attempt.
                        value["attempts"] = max(
                            0,
                            int(value.get("attempts", 0)) - 1,
                        )
                        value["next_run_at"] = (
                            now
                            + timedelta(
                                seconds=self.APPROVAL_LEASE_RETRY_SECONDS
                            )
                        ).isoformat()
                        value["last_error"] = (
                            "Jednorazowa zgoda jest nadal aktywna; "
                            "wznawiam kolejny bezpieczny etap tego samego "
                            "przebiegu."
                        )
                        value["last_result"] = {
                            **dict(value.get("last_result", {}) or {}),
                            "status": "AUTONOMOUS_APPROVAL_LEASE_CONTINUES",
                            "phase": "APPROVAL_LEASE_RESUME",
                            "approval_lease_state": "ACTIVE",
                            "approval_lease_id": str(
                                lease.get("lease_id", "")
                            ),
                            "requires_approval": False,
                        }
                        saved = self.store.save_job(value)
                        self.store.record_event(
                            "LONG_RUNNING_APPROVAL_LEASE_CONTINUES",
                            job_id=str(value.get("job_id", "")),
                            metadata={
                                "diagnostic_id": str(
                                    diagnostic.get("diagnostic_id", "")
                                ),
                                "lease_id": str(
                                    lease.get("lease_id", "")
                                ),
                                "cycle": cycles,
                                "max_cycles": maximum,
                            },
                        )
                        return saved
                    self._finish_approval_lease(
                        value,
                        state="EXPIRED_CYCLE_LIMIT",
                        now=now,
                    )

                value["state"] = "WAITING_APPROVAL"
                value["next_run_at"] = ""
                value["last_error"] = str(
                    diagnostic.get(
                        "root_cause",
                        "Przebieg czeka na jawne zatwierdzenie.",
                    )
                )[:4000]
                saved = self.store.save_job(value)
                self.store.record_event(
                    "LONG_RUNNING_JOB_WAITING_APPROVAL",
                    job_id=str(value.get("job_id", "")),
                    metadata={
                        "diagnostic_id": str(
                            diagnostic.get("diagnostic_id", "")
                        ),
                        "category": str(
                            diagnostic.get("category", "")
                        ),
                    },
                )
                return saved

            value["last_error"] = str(
                diagnostic.get(
                    "root_cause",
                    "Przebieg pełnej autonomii został wstrzymany.",
                )
            )[:4000]
            if self._attempts_exhausted(value):
                return self._fail_attempts_exhausted(
                    value,
                    now=now,
                    last_status=status,
                )

            value["state"] = "SCHEDULED"
            value["next_run_at"] = (
                now + timedelta(
                    seconds=float(
                        self.store.policy().get(
                            "failure_retry_seconds", 120.0
                        )
                    )
                )
            ).isoformat()
            saved = self.store.save_job(value)
            self.store.record_event(
                "LONG_RUNNING_JOB_AUTONOMY_PAUSED",
                job_id=str(value.get("job_id", "")),
                metadata={
                    "attempt": int(value.get("attempts", 0)),
                    "max_attempts": int(
                        value.get("max_attempts", 3)
                    ),
                },
            )
            return saved

        errors = response.get("errors", [])
        value["last_error"] = str(
            diagnostic.get("root_cause", "")
        ).strip() or "; ".join(
            str(item) for item in errors
        ) or status or "Nieznany błąd wykonania."
        if int(value.get("attempts", 0)) < int(
            value.get("max_attempts", 3)
        ):
            value["state"] = "SCHEDULED"
            value["next_run_at"] = (
                now + timedelta(
                    seconds=float(
                        self.store.policy().get(
                            "failure_retry_seconds", 120.0
                        )
                    )
                )
            ).isoformat()
            event = "LONG_RUNNING_JOB_RETRY_SCHEDULED"
        else:
            value["state"] = "FAILED"
            value["completed_at"] = now.isoformat()
            value["next_run_at"] = ""
            self._finish_approval_lease(
                value,
                state="CONSUMED_TERMINAL_FAILURE",
                now=now,
            )
            event = "LONG_RUNNING_JOB_FAILED"

        saved = self.store.save_job(value)
        self.store.record_event(
            event,
            job_id=str(value.get("job_id", "")),
            metadata={"status": status},
        )
        return saved

    @staticmethod
    def _is_constraints_pause(
        response: dict[str, Any],
        diagnostic: dict[str, Any],
    ) -> bool:
        if str(diagnostic.get("category", "")).upper() == "CONSTRAINTS_PAUSE":
            return True

        markers = {
            "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS",
            "MULTI_CAMPAIGN_PAUSED_CONSTRAINTS",
            "PORTFOLIO_PAUSED_CONSTRAINTS",
            "SCORE_BELOW_MINIMUM",
            "CONSTRAINTS_PAUSE",
        }
        evidence_keys = {
            "status",
            "state",
            "event",
            "director_status",
            "portfolio_status",
            "reason",
            "reasons",
            "error",
            "errors",
        }

        def walk(value: Any, *, key: str = "", depth: int = 0) -> bool:
            if depth > 10:
                return False
            if isinstance(value, dict):
                for child_key, child in value.items():
                    normalized = str(child_key).casefold()
                    if normalized in evidence_keys and walk(
                        child,
                        key=normalized,
                        depth=depth + 1,
                    ):
                        return True
                    if isinstance(child, (dict, list)) and walk(
                        child,
                        key=normalized,
                        depth=depth + 1,
                    ):
                        return True
                return False
            if isinstance(value, list):
                return any(
                    walk(item, key=key, depth=depth + 1)
                    for item in value[:200]
                )
            if key not in evidence_keys:
                return False
            return str(value).strip().upper() in markers

        return walk(response)

    def _run_workflow(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = str(job.get("autonomy_run_id", "")).strip()
        if run_id:
            current = self.workflow.status(run_id)
            status = str(current.get("status", "")).upper()
            if status == "FULL_AUTONOMY_COMPLETED":
                return current
            if status in {
                "FULL_AUTONOMY_PLAN_READY",
                "FULL_AUTONOMY_PORTFOLIO_READY",
                "FULL_AUTONOMY_PAUSED",
                "FULL_AUTONOMY_RUNNING",
            }:
                return self.workflow.execute(
                    run_id,
                    context=self._safe_execution_context(
                        dict(job.get("execution_context", {}) or {})
                    ),
                )

        return self.workflow.run(
            str(job.get("objective", "")),
            context=self._safe_execution_context(
                dict(job.get("execution_context", {}) or {})
            ),
        )

    def _defer_constraints_pause(
        self,
        job: dict[str, Any],
        response: dict[str, Any],
        *,
        diagnostic: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        value = dict(job)
        value["state"] = "CANCELLED"
        value["completed_at"] = now.isoformat()
        value["next_run_at"] = ""
        value["last_error"] = str(
            diagnostic.get(
                "root_cause",
                "Zadanie odroczono, ponieważ nie spełnia ograniczeń wykonania.",
            )
        )[:4000]
        value["last_result"] = {
            **dict(value.get("last_result", {}) or {}),
            "success": True,
            "status": "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS",
            "source_status": str(response.get("status", "")),
            "phase": "DEFERRED_CONSTRAINTS",
            "deferred": True,
            "diagnostic_category": "CONSTRAINTS_PAUSE",
            "updated_at": now.isoformat(),
        }
        self._finish_approval_lease(
            value,
            state="CONSUMED_DEFERRED_CONSTRAINTS",
            now=now,
        )
        saved = self.store.save_job(value)
        self.store.record_event(
            "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS",
            job_id=str(value.get("job_id", "")),
            metadata={
                "diagnostic_id": str(diagnostic.get("diagnostic_id", "")),
                "attempt": int(value.get("attempts", 0) or 0),
            },
        )
        return saved

    def _complete_job(
        self,
        job: dict[str, Any],
        response: dict[str, Any],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        history = list(job.get("run_history", []) or [])
        history.append({
            "autonomy_run_id": str(
                response.get("autonomy_run_id", "")
            ),
            "status": str(response.get("status", "")),
            "completed_at": now.isoformat(),
            "attempt": int(job.get("attempts", 0)),
        })
        job["run_history"] = history[-50:]
        job["last_error"] = ""

        schedule = dict(job.get("schedule", {}) or {})
        if self.scheduler.is_recurring(schedule):
            job["state"] = "SCHEDULED"
            job["next_run_at"] = self.scheduler.next_after_success(
                schedule,
                now=now,
            )
            job["autonomy_run_id"] = ""
            job["attempts"] = 0
            job["started_at"] = ""
            job["completed_at"] = ""
            event = "LONG_RUNNING_JOB_RESCHEDULED"
        else:
            job["state"] = "COMPLETED"
            job["completed_at"] = now.isoformat()
            event = "LONG_RUNNING_JOB_COMPLETED"

        saved = self.store.save_job(job)
        self.store.record_event(
            event,
            job_id=str(job.get("job_id", "")),
        )
        return saved

    def _set_job_state(
        self,
        job_id: str,
        state: str,
    ) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if job is None:
            return self._job_not_found(job_id)
        if str(job.get("state", "")).upper() in TERMINAL_JOB_STATES:
            return self._response(
                "LONG_RUNNING_JOB_TERMINAL",
                job=job,
                success=False,
                errors=["Zadanie ma już status końcowy."],
            )
        job["state"] = state
        if state == "CANCELLED":
            job["completed_at"] = self._utc(self.clock()).isoformat()
        saved = self.store.save_job(job)
        self.store.record_event(
            f"LONG_RUNNING_JOB_{state}",
            job_id=job_id,
        )
        return self._response(
            f"LONG_RUNNING_JOB_{state}",
            job=saved,
            success=True,
        )

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as error:
                self.store.update_runtime({
                    "last_error": f"{type(error).__name__}: {error}",
                })
            interval = float(
                self.store.policy().get("interval_seconds", 15.0)
            )
            if self._stop_event.wait(timeout=interval):
                break
        self.store.update_runtime({"running": False})

    def _cycle_result(
        self,
        status: str,
        jobs: list[dict[str, Any]],
        now: datetime,
        *,
        recovered: int = 0,
    ) -> dict[str, Any]:
        result = self._response(
            status,
            success=True,
            jobs=jobs,
            recovered=recovered,
        )
        runtime = self.store.runtime()
        self.store.update_runtime({
            "last_result": self.store.compact_result(result),
            "last_error": "",
            "last_tick_at": now.isoformat(),
            "heartbeat_at": now.isoformat(),
            "cycles_completed": int(
                runtime.get("cycles_completed", 0)
            ) + 1,
        })
        return result

    def _safe_execution_context(
        self,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        policy = self.store.policy()
        result = dict(values)
        lease = dict(result.get("_b54_approval_lease", {}) or {})
        one_time_auto_approve = bool(
            result.get("_b54_one_time_auto_approve", False)
            or str(lease.get("state", "")).upper() == "ACTIVE"
        )
        result.update({
            "auto_execute": True,
            "auto_approve": one_time_auto_approve,
            "auto_rollback": bool(
                result.get(
                    "auto_rollback",
                    policy.get("auto_rollback", True),
                )
            ),
            "final_validation": bool(
                result.get(
                    "final_validation",
                    policy.get("final_validation", True),
                )
            ),
        })
        result.pop("schedule", None)
        result.pop("resource_policy", None)
        return result

    def _refresh_job_monitoring(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        """Return live progress without overwriting supervisor state."""
        value = dict(job)
        state = str(value.get("state", "")).upper()
        run_id = str(value.get("autonomy_run_id", "")).strip()
        if state not in {"RUNNING", "SCHEDULED", "RECOVERING"} or not run_id:
            self._decorate_result_with_approval_lease(value)
            return value
        try:
            current = self.workflow.status(run_id)
        except Exception:
            self._decorate_result_with_approval_lease(value)
            return value
        if not isinstance(current, dict):
            self._decorate_result_with_approval_lease(value)
            return value
        monitored = self.store.compact_result(current)
        if monitored:
            monitored.setdefault("autonomy_run_id", run_id)
            monitored.setdefault("phase", "EXECUTING_FULL_AUTONOMY")
            value["last_result"] = monitored
            execution = dict(current.get("execution", {}) or {})
            updated_at = str(execution.get("updated_at", "")).strip()
            if updated_at:
                value["heartbeat_at"] = updated_at
        self._decorate_result_with_approval_lease(value)
        return value

    def _current_progress(self, job: dict[str, Any]) -> float:
        run_id = str(job.get("autonomy_run_id", "")).strip()
        if not run_id:
            return 0.0
        try:
            current = self.workflow.status(run_id)
        except Exception:
            return 0.0
        if not isinstance(current, dict):
            return 0.0
        execution = dict(current.get("execution", {}) or {})
        try:
            return float(
                current.get(
                    "progress_percent",
                    execution.get("progress_percent", 0.0),
                )
                or 0.0
            )
        except (TypeError, ValueError):
            return 0.0

    def _approval_lease(
        self,
        job: dict[str, Any],
    ) -> dict[str, Any]:
        context = dict(job.get("execution_context", {}) or {})
        lease = dict(context.get("_b54_approval_lease", {}) or {})
        if not lease and bool(
            context.get("_b54_one_time_auto_approve", False)
        ):
            lease = {
                "lease_id": str(context.get("_b54_repair_id", "")),
                "repair_id": str(context.get("_b54_repair_id", "")),
                "state": "ACTIVE",
                "scope": "FULL_AUTONOMY_RUN",
                "autonomy_run_id": str(job.get("autonomy_run_id", "")),
                "cycles": 0,
                "max_cycles": self.APPROVAL_LEASE_MAX_CYCLES,
            }
        return lease

    def _approval_lease_active(
        self,
        job: dict[str, Any],
    ) -> bool:
        lease = self._approval_lease(job)
        if str(lease.get("state", "")).upper() != "ACTIVE":
            return False
        scoped_run = str(lease.get("autonomy_run_id", "")).strip()
        current_run = str(job.get("autonomy_run_id", "")).strip()
        return not scoped_run or not current_run or scoped_run == current_run

    def _advance_approval_lease(
        self,
        job: dict[str, Any],
        *,
        now: datetime,
    ) -> dict[str, Any]:
        if not self._approval_lease_active(job):
            return {}
        context = dict(job.get("execution_context", {}) or {})
        lease = self._approval_lease(job)
        lease["state"] = "ACTIVE"
        lease["cycles"] = int(lease.get("cycles", 0) or 0) + 1
        lease["max_cycles"] = min(
            20,
            max(
                1,
                int(
                    lease.get(
                        "max_cycles",
                        self.APPROVAL_LEASE_MAX_CYCLES,
                    )
                    or self.APPROVAL_LEASE_MAX_CYCLES
                ),
            ),
        )
        lease.setdefault("autonomy_run_id", str(job.get("autonomy_run_id", "")))
        lease["last_forwarded_at"] = now.isoformat()
        context["_b54_approval_lease"] = lease
        context["_b54_one_time_auto_approve"] = True
        context["_b54_repair_id"] = str(
            lease.get("repair_id", lease.get("lease_id", ""))
        )
        metadata = dict(job.get("metadata", {}) or {})
        metadata["b54_approval_lease_state"] = "ACTIVE"
        metadata["b54_approval_lease_id"] = str(lease.get("lease_id", ""))
        metadata["b54_approval_lease_cycles"] = int(lease.get("cycles", 0))
        job["execution_context"] = context
        job["metadata"] = metadata
        return lease

    def _finish_approval_lease(
        self,
        job: dict[str, Any],
        *,
        state: str,
        now: datetime,
    ) -> None:
        context = dict(job.get("execution_context", {}) or {})
        lease = self._approval_lease(job)
        context.pop("_b54_approval_lease", None)
        context.pop("_b54_one_time_auto_approve", None)
        context.pop("_b54_repair_id", None)
        metadata = dict(job.get("metadata", {}) or {})
        metadata["b54_approval_lease_state"] = str(state)
        metadata["b54_approval_lease_completed_at"] = now.isoformat()
        metadata["b54_repair_approval_consumed"] = True
        if lease:
            metadata["b54_approval_lease_id"] = str(
                lease.get("lease_id", "")
            )
            metadata["b54_repair_approval_consumed_id"] = str(
                lease.get("repair_id", lease.get("lease_id", ""))
            )
            metadata["b54_approval_lease_cycles"] = int(
                lease.get("cycles", 0) or 0
            )
        job["execution_context"] = context
        job["metadata"] = metadata
        self._decorate_result_with_approval_lease(job)

    def _decorate_result_with_approval_lease(
        self,
        job: dict[str, Any],
    ) -> None:
        result = dict(job.get("last_result", {}) or {})
        if self._approval_lease_active(job):
            lease = self._approval_lease(job)
            result["approval_lease_state"] = "ACTIVE"
            result["approval_lease_id"] = str(
                lease.get("lease_id", "")
            )
        else:
            state = str(
                dict(job.get("metadata", {}) or {}).get(
                    "b54_approval_lease_state",
                    "",
                )
            ).strip()
            if state:
                result["approval_lease_state"] = state
        job["last_result"] = result

    @staticmethod
    def _schedule_from_context(
        values: dict[str, Any],
    ) -> dict[str, Any]:
        if values.get("run_at"):
            return {
                "type": "once",
                "run_at": values.get("run_at"),
            }
        if values.get("interval_minutes"):
            return {
                "type": "interval",
                "interval_minutes": values.get("interval_minutes"),
            }
        if values.get("daily_at"):
            text = str(values.get("daily_at"))
            match = re.match(r"^(\d{1,2}):(\d{2})$", text)
            if match:
                return {
                    "type": "daily",
                    "hour": int(match.group(1)),
                    "minute": int(match.group(2)),
                }
        return {"type": "immediate"}

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _bounded_int(
        value: Any,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = minimum
        return min(maximum, max(minimum, parsed))

    def _job_not_found(self, job_id: str) -> dict[str, Any]:
        return self._response(
            "LONG_RUNNING_JOB_NOT_FOUND",
            success=False,
            errors=[f"Nie znaleziono zadania {job_id}."],
        )

    def _error(
        self,
        status: str,
        errors: list[str],
    ) -> dict[str, Any]:
        return self._response(
            status,
            success=False,
            errors=errors,
        )

    def _response(
        self,
        status: str,
        *,
        success: bool,
        job: dict[str, Any] | None = None,
        jobs: list[dict[str, Any]] | None = None,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "long_running_autonomy",
            "job_id": str((job or {}).get("job_id", "")),
            "job": dict(job or {}),
            "jobs": list(jobs or []),
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }


def bootstrap_long_running_autonomy(
    controller: Any,
) -> LongRunningAutonomyService:
    service = getattr(
        controller,
        "long_running_autonomy_service",
        None,
    )
    if service is None:
        service = LongRunningAutonomyService(
            controller.project_root
        )
        controller.long_running_autonomy_service = service
    service.start_if_enabled()
    return service

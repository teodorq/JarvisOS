"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import threading
import time
import uuid

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable, Iterable

from app.autodev.autonomous_task_queue import (
    AutonomousTask,
    AutonomousTaskQueue,
    RetryPolicy,
    TaskPriority,
    TaskStatus,
)


class SchedulerState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    FAILED = "failed"


class DispatchDecision(StrEnum):
    DISPATCHED = "dispatched"
    NO_TASK = "no_task"
    NO_WORKER = "no_worker"
    PAUSED = "paused"
    STOPPED = "stopped"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass(slots=True)
class SchedulerPolicy:
    poll_interval_seconds: float = 1.0
    idle_backoff_seconds: float = 2.0
    max_parallel_tasks: int = 1
    stale_task_timeout_seconds: float = 1800.0
    recover_stale_tasks: bool = True
    autosave_queue: bool = True

    def validate(self) -> None:
        if self.poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than 0"
            )

        if self.idle_backoff_seconds <= 0:
            raise ValueError(
                "idle_backoff_seconds must be greater than 0"
            )

        if self.max_parallel_tasks < 1:
            raise ValueError(
                "max_parallel_tasks must be at least 1"
            )

        if self.stale_task_timeout_seconds <= 0:
            raise ValueError(
                "stale_task_timeout_seconds must be greater than 0"
            )


@dataclass(slots=True)
class WorkerRegistration:
    worker_id: str
    handler: Callable[[AutonomousTask], Any]
    accepted_sources: set[str] = field(default_factory=set)
    required_tags: set[str] = field(default_factory=set)
    enabled: bool = True
    busy: bool = False
    current_task_id: str | None = None
    registered_at: float = field(default_factory=time.time)
    last_started_at: float | None = None
    last_finished_at: float | None = None
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_seconds: float = 0.0

    @property
    def average_execution_seconds(self) -> float:
        finished = self.completed_tasks + self.failed_tasks
        if finished <= 0:
            return 0.0
        return self.total_execution_seconds / finished

    def accepts(self, task: AutonomousTask) -> bool:
        if not self.enabled or self.busy:
            return False

        if (
            self.accepted_sources
            and task.source not in self.accepted_sources
        ):
            return False

        if (
            self.required_tags
            and not self.required_tags.issubset(set(task.tags))
        ):
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "accepted_sources": sorted(self.accepted_sources),
            "required_tags": sorted(self.required_tags),
            "enabled": self.enabled,
            "busy": self.busy,
            "current_task_id": self.current_task_id,
            "registered_at": self.registered_at,
            "last_started_at": self.last_started_at,
            "last_finished_at": self.last_finished_at,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_execution_seconds": self.total_execution_seconds,
            "average_execution_seconds": self.average_execution_seconds,
        }


@dataclass(slots=True)
class DispatchRecord:
    dispatch_id: str
    task_id: str
    worker_id: str
    started_at: float
    finished_at: float | None = None
    success: bool | None = None
    error: str | None = None
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration_seconds"] = (
            None
            if self.finished_at is None
            else max(0.0, self.finished_at - self.started_at)
        )
        return data


@dataclass(slots=True)
class SchedulerMetrics:
    dispatch_attempts: int = 0
    dispatched_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    retried_tasks: int = 0
    rejected_tasks: int = 0
    worker_errors: int = 0
    idle_cycles: int = 0
    active_tasks: int = 0
    registered_workers: int = 0
    total_execution_seconds: float = 0.0
    average_execution_seconds: float = 0.0

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


class AutoDevScheduler:
    """
    Central scheduler for autonomous AutoDev tasks.

    Responsibilities:
    - select the next runnable task,
    - match it to a compatible worker,
    - enforce parallelism limits,
    - execute tasks in background threads,
    - complete or fail queue tasks,
    - recover stale tasks,
    - expose scheduler and worker metrics.
    """

    def __init__(
        self,
        queue: AutonomousTaskQueue,
        *,
        policy: SchedulerPolicy | None = None,
        scheduler_id: str | None = None,
    ) -> None:
        self.queue = queue
        self.policy = policy or SchedulerPolicy()
        self.policy.validate()

        self.scheduler_id = (
            scheduler_id.strip()
            if scheduler_id and scheduler_id.strip()
            else f"autodev-scheduler-{uuid.uuid4()}"
        )

        self._state = SchedulerState.STOPPED
        self._workers: dict[str, WorkerRegistration] = {}
        self._active_threads: dict[str, threading.Thread] = {}
        self._dispatch_records: list[DispatchRecord] = []
        self._metrics = SchedulerMetrics()

        self._lock = threading.RLock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._loop_thread: threading.Thread | None = None
        self._last_error: str | None = None

    @property
    def state(self) -> SchedulerState:
        with self._lock:
            return self._state

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def register_worker(
        self,
        worker_id: str,
        handler: Callable[[AutonomousTask], Any],
        *,
        accepted_sources: Iterable[str] | None = None,
        required_tags: Iterable[str] | None = None,
        enabled: bool = True,
        replace: bool = False,
    ) -> WorkerRegistration:
        worker_id = worker_id.strip()

        if not worker_id:
            raise ValueError("worker_id cannot be empty")

        if not callable(handler):
            raise TypeError("handler must be callable")

        registration = WorkerRegistration(
            worker_id=worker_id,
            handler=handler,
            accepted_sources={
                str(source).strip()
                for source in (accepted_sources or [])
                if str(source).strip()
            },
            required_tags={
                str(tag).strip().lower()
                for tag in (required_tags or [])
                if str(tag).strip()
            },
            enabled=enabled,
        )

        with self._lock:
            if worker_id in self._workers and not replace:
                raise ValueError(
                    f"Worker {worker_id!r} is already registered"
                )

            current = self._workers.get(worker_id)
            if current is not None and current.busy:
                raise RuntimeError(
                    f"Cannot replace busy worker {worker_id!r}"
                )

            self._workers[worker_id] = registration
            self._wake_event.set()
            return registration

    def unregister_worker(
        self,
        worker_id: str,
        *,
        force: bool = False,
    ) -> bool:
        with self._lock:
            worker = self._workers.get(worker_id)

            if worker is None:
                return False

            if worker.busy and not force:
                raise RuntimeError(
                    f"Worker {worker_id!r} is currently busy"
                )

            del self._workers[worker_id]
            return True

    def enable_worker(
        self,
        worker_id: str,
        enabled: bool = True,
    ) -> WorkerRegistration:
        with self._lock:
            worker = self._require_worker(worker_id)
            worker.enabled = enabled
            self._wake_event.set()
            return worker

    def _require_worker(
        self,
        worker_id: str,
    ) -> WorkerRegistration:
        worker = self._workers.get(worker_id)

        if worker is None:
            raise KeyError(f"Unknown worker: {worker_id}")

        return worker

    def list_workers(self) -> list[dict[str, Any]]:
        with self._lock:
            workers = [
                worker.to_dict()
                for worker in self._workers.values()
            ]
            workers.sort(key=lambda item: item["worker_id"])
            return workers

    def start(self) -> bool:
        with self._lock:
            if self._state in {
                SchedulerState.STARTING,
                SchedulerState.RUNNING,
            }:
                return False

            if self._state == SchedulerState.STOPPING:
                raise RuntimeError(
                    "Scheduler is currently stopping"
                )

            self._state = SchedulerState.STARTING
            self._last_error = None
            self._stop_event.clear()
            self._wake_event.clear()

            self._loop_thread = threading.Thread(
                target=self._run_loop,
                name=self.scheduler_id,
                daemon=True,
            )
            self._loop_thread.start()
            return True

    def stop(
        self,
        *,
        wait: bool = True,
        timeout: float | None = None,
    ) -> bool:
        with self._lock:
            if self._state == SchedulerState.STOPPED:
                return False

            self._state = SchedulerState.STOPPING
            self._stop_event.set()
            self._wake_event.set()
            loop_thread = self._loop_thread

        if wait and loop_thread is not None:
            loop_thread.join(timeout=timeout)

        if wait:
            self.wait_for_active_tasks(timeout=timeout)

        with self._lock:
            if (
                self._loop_thread is None
                or not self._loop_thread.is_alive()
            ):
                self._state = SchedulerState.STOPPED
                self._loop_thread = None

        return True

    def pause(self) -> bool:
        with self._lock:
            if self._state != SchedulerState.RUNNING:
                return False

            self._state = SchedulerState.PAUSED
            return True

    def resume(self) -> bool:
        with self._lock:
            if self._state != SchedulerState.PAUSED:
                return False

            self._state = SchedulerState.RUNNING
            self._wake_event.set()
            return True

    def wake(self) -> None:
        self._wake_event.set()

    def _run_loop(self) -> None:
        try:
            with self._lock:
                self._state = SchedulerState.RUNNING

            while not self._stop_event.is_set():
                if self.state == SchedulerState.PAUSED:
                    self._wake_event.wait(
                        timeout=self.policy.poll_interval_seconds
                    )
                    self._wake_event.clear()
                    continue

                if self.policy.recover_stale_tasks:
                    self.recover_stale_tasks()

                decision = self.dispatch_once()

                if decision in {
                    DispatchDecision.NO_TASK,
                    DispatchDecision.NO_WORKER,
                }:
                    with self._lock:
                        self._metrics.idle_cycles += 1

                    self._wake_event.wait(
                        timeout=self.policy.idle_backoff_seconds
                    )
                else:
                    self._wake_event.wait(
                        timeout=self.policy.poll_interval_seconds
                    )

                self._wake_event.clear()

        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
                self._state = SchedulerState.FAILED

        finally:
            with self._lock:
                if self._state != SchedulerState.FAILED:
                    self._state = SchedulerState.STOPPED
                self._loop_thread = None

    def dispatch_once(self) -> DispatchDecision:
        with self._lock:
            self._metrics.dispatch_attempts += 1

            if self._state == SchedulerState.PAUSED:
                return DispatchDecision.PAUSED

            if self._state in {
                SchedulerState.STOPPED,
                SchedulerState.STOPPING,
                SchedulerState.FAILED,
            }:
                return DispatchDecision.STOPPED

            self._cleanup_finished_threads()

            if (
                len(self._active_threads)
                >= self.policy.max_parallel_tasks
            ):
                return DispatchDecision.NO_WORKER

            workers = self._available_workers()

            if not workers:
                return DispatchDecision.NO_WORKER

        worker: WorkerRegistration | None = None
        task: AutonomousTask | None = None

        for candidate in workers:
            claimed = self.queue.claim_next(
                candidate.worker_id,
                accepted_sources=(
                    candidate.accepted_sources
                    if candidate.accepted_sources
                    else None
                ),
                required_tags=(
                    candidate.required_tags
                    if candidate.required_tags
                    else None
                ),
            )

            if claimed is not None:
                worker = candidate
                task = claimed
                break

        if worker is None or task is None:
            return DispatchDecision.NO_TASK

        with self._lock:
            if not worker.accepts(task):
                self.queue.release(
                    task.task_id,
                    worker_id=worker.worker_id,
                )
                self._metrics.rejected_tasks += 1
                return DispatchDecision.REJECTED

            worker.busy = True
            worker.current_task_id = task.task_id
            worker.last_started_at = time.time()

            dispatch = DispatchRecord(
                dispatch_id=str(uuid.uuid4()),
                task_id=task.task_id,
                worker_id=worker.worker_id,
                started_at=time.time(),
            )
            self._dispatch_records.append(dispatch)

            thread = threading.Thread(
                target=self._execute_task,
                args=(worker.worker_id, task, dispatch),
                name=(
                    f"{self.scheduler_id}:"
                    f"{worker.worker_id}:"
                    f"{task.task_id}"
                ),
                daemon=True,
            )
            self._active_threads[task.task_id] = thread
            self._metrics.dispatched_tasks += 1
            thread.start()
            return DispatchDecision.DISPATCHED

    def _available_workers(self) -> list[WorkerRegistration]:
        workers = [
            worker
            for worker in self._workers.values()
            if worker.enabled and not worker.busy
        ]

        workers.sort(
            key=lambda worker: (
                worker.completed_tasks + worker.failed_tasks,
                worker.registered_at,
                worker.worker_id,
            )
        )
        return workers

    def _select_available_worker(
        self,
    ) -> WorkerRegistration | None:
        workers = self._available_workers()
        return workers[0] if workers else None

    def _execute_task(
        self,
        worker_id: str,
        task: AutonomousTask,
        dispatch: DispatchRecord,
    ) -> None:
        worker: WorkerRegistration | None = None

        try:
            with self._lock:
                worker = self._workers.get(worker_id)

            if worker is None:
                raise RuntimeError(
                    f"Worker {worker_id!r} disappeared"
                )

            raw_result = worker.handler(task)
            normalized_result = self._normalize_result(raw_result)

            self.queue.complete(
                task.task_id,
                result=normalized_result,
                worker_id=worker_id,
            )

            with self._lock:
                worker.completed_tasks += 1
                dispatch.success = True
                dispatch.result = normalized_result
                self._metrics.completed_tasks += 1

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

            retry_scheduled = False

            try:
                current = self.queue.get(task.task_id)
                if (
                    current is not None
                    and current.status == TaskStatus.RUNNING
                ):
                    failed_task = self.queue.fail(
                        task.task_id,
                        error,
                        worker_id=worker_id,
                        retryable=True,
                    )
                    retry_scheduled = (
                        failed_task.status == TaskStatus.RETRY_WAIT
                    )
            except Exception as queue_exc:
                error = (
                    f"{error}; queue failure: "
                    f"{type(queue_exc).__name__}: {queue_exc}"
                )

            with self._lock:
                if worker is not None:
                    worker.failed_tasks += 1

                dispatch.success = False
                dispatch.error = error

                if retry_scheduled:
                    self._metrics.retried_tasks += 1
                else:
                    self._metrics.failed_tasks += 1

                self._metrics.worker_errors += 1

        finally:
            finished_at = time.time()
            duration_seconds = max(
                0.0,
                finished_at - dispatch.started_at,
            )

            with self._lock:
                dispatch.finished_at = finished_at
                self._metrics.total_execution_seconds += (
                    duration_seconds
                )

                finished_tasks = (
                    self._metrics.completed_tasks
                    + self._metrics.failed_tasks
                    + self._metrics.retried_tasks
                )
                self._metrics.average_execution_seconds = (
                    self._metrics.total_execution_seconds
                    / finished_tasks
                    if finished_tasks > 0
                    else 0.0
                )

                if worker is not None:
                    worker.total_execution_seconds += duration_seconds
                    worker.busy = False
                    worker.current_task_id = None
                    worker.last_finished_at = finished_at

                self._active_threads.pop(task.task_id, None)
                self._wake_event.set()

    def _normalize_result(
        self,
        result: Any,
    ) -> dict[str, Any]:
        if result is None:
            return {}

        if isinstance(result, dict):
            return dict(result)

        if hasattr(result, "to_dict"):
            converted = result.to_dict()
            if isinstance(converted, dict):
                return converted

        return {"value": result}

    def _cleanup_finished_threads(self) -> None:
        finished = [
            task_id
            for task_id, thread in self._active_threads.items()
            if not thread.is_alive()
        ]

        for task_id in finished:
            self._active_threads.pop(task_id, None)

    def recover_stale_tasks(self) -> int:
        now = time.time()
        recovered = 0

        running_tasks = self.queue.list_tasks(
            statuses=[TaskStatus.RUNNING]
        )

        for task in running_tasks:
            if task.started_at is None:
                continue

            elapsed = now - task.started_at
            if elapsed < self.policy.stale_task_timeout_seconds:
                continue

            with self._lock:
                thread = self._active_threads.get(task.task_id)

            if thread is not None and thread.is_alive():
                continue

            try:
                self.queue.release(
                    task.task_id,
                    worker_id=task.claimed_by,
                )
                recovered += 1
            except Exception:
                continue

        if recovered:
            self._wake_event.set()

        return recovered

    def submit_task(
        self,
        title: str,
        description: str,
        *,
        source: str = "autodev_scheduler",
        priority: TaskPriority = TaskPriority.NORMAL,
        payload: dict[str, Any] | None = None,
        tags: Iterable[str] | None = None,
        dependencies: Iterable[str] | None = None,
        retry_policy: RetryPolicy | None = None,
        scheduled_for: float | None = None,
        timeout_seconds: float | None = None,
        reject_duplicates: bool = True,
    ) -> AutonomousTask:
        task = self.queue.create_task(
            title=title,
            description=description,
            source=source,
            priority=priority,
            payload=payload,
            tags=tags,
            dependencies=dependencies,
            retry_policy=retry_policy,
            scheduled_for=scheduled_for,
            timeout_seconds=timeout_seconds,
            reject_duplicates=reject_duplicates,
        )
        self._wake_event.set()
        return task

    def wait_for_active_tasks(
        self,
        *,
        timeout: float | None = None,
    ) -> bool:
        deadline = (
            None
            if timeout is None
            else time.time() + timeout
        )

        while True:
            with self._lock:
                threads = list(self._active_threads.values())

            if not threads:
                return True

            for thread in threads:
                remaining = (
                    None
                    if deadline is None
                    else max(0.0, deadline - time.time())
                )

                if remaining == 0.0:
                    return False

                thread.join(timeout=remaining)

            if deadline is not None and time.time() >= deadline:
                return False

    def wait_until_idle(
        self,
        *,
        timeout: float | None = None,
        poll_interval: float = 0.1,
    ) -> bool:
        if poll_interval <= 0:
            raise ValueError(
                "poll_interval must be greater than 0"
            )

        deadline = (
            None
            if timeout is None
            else time.time() + timeout
        )

        while True:
            with self._lock:
                self._cleanup_finished_threads()
                active = bool(self._active_threads)
                busy = any(
                    worker.busy
                    for worker in self._workers.values()
                )

            if not active and not busy:
                return True

            if (
                deadline is not None
                and time.time() >= deadline
            ):
                return False

            time.sleep(poll_interval)

    def metrics(self) -> SchedulerMetrics:
        with self._lock:
            self._cleanup_finished_threads()
            return SchedulerMetrics(
                dispatch_attempts=self._metrics.dispatch_attempts,
                dispatched_tasks=self._metrics.dispatched_tasks,
                completed_tasks=self._metrics.completed_tasks,
                failed_tasks=self._metrics.failed_tasks,
                retried_tasks=self._metrics.retried_tasks,
                rejected_tasks=self._metrics.rejected_tasks,
                worker_errors=self._metrics.worker_errors,
                idle_cycles=self._metrics.idle_cycles,
                active_tasks=len(self._active_threads),
                registered_workers=len(self._workers),
                total_execution_seconds=(
                    self._metrics.total_execution_seconds
                ),
                average_execution_seconds=(
                    self._metrics.average_execution_seconds
                ),
            )

    def dispatch_history(
        self,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            records = list(self._dispatch_records)
            records.sort(
                key=lambda record: record.started_at,
                reverse=True,
            )

            if limit is not None:
                records = records[: max(0, limit)]

            return [
                record.to_dict()
                for record in records
            ]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "scheduler_id": self.scheduler_id,
                "state": self._state.value,
                "last_error": self._last_error,
                "policy": asdict(self.policy),
                "metrics": self.metrics().to_dict(),
                "workers": self.list_workers(),
                "dispatch_history": self.dispatch_history(),
                "queue": self.queue.export_snapshot(),
            }

    def is_running(self) -> bool:
        return self.state == SchedulerState.RUNNING

    def is_paused(self) -> bool:
        return self.state == SchedulerState.PAUSED

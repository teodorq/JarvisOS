from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from app.autodev.autodev_scheduler import (
    AutoDevScheduler,
    SchedulerPolicy,
    SchedulerState,
)
from app.autodev.autodev_worker import (
    AutoDevWorker,
    AutoDevWorkerPolicy,
)
from app.autodev.autodev_pipeline_task_service import (
    AutoDevPipelineTaskService,
)
from app.autodev.autonomous_task_queue import (
    AutonomousTask,
    AutonomousTaskQueue,
    RetryPolicy,
    TaskPriority,
    TaskStatus,
)


_AUTODEV_PIPELINE_TASKS = AutoDevPipelineTaskService()


from app.autodev.error_reporting import AutoDevErrorReporter

@dataclass(slots=True)
class AutoDevPipelinePolicy:
    project_root: str = default_project_root()
    queue_storage_path: str = (
        "data/autodev/autonomous_task_queue.json"
    )
    worker_count: int = 1
    auto_approve: bool = False
    auto_execute: bool = True
    auto_rollback: bool = True
    max_parallel_tasks: int = 1
    poll_interval_seconds: float = 1.0
    idle_backoff_seconds: float = 2.0
    stale_task_timeout_seconds: float = 1800.0

    def validate(self) -> None:
        if not self.project_root.strip():
            raise ValueError("project_root cannot be empty")

        if not self.queue_storage_path.strip():
            raise ValueError(
                "queue_storage_path cannot be empty"
            )

        if self.worker_count < 1:
            raise ValueError(
                "worker_count must be at least 1"
            )

        if self.max_parallel_tasks < 1:
            raise ValueError(
                "max_parallel_tasks must be at least 1"
            )

        if self.max_parallel_tasks > self.worker_count:
            raise ValueError(
                "max_parallel_tasks cannot exceed worker_count"
            )

        if self.poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than 0"
            )

        if self.idle_backoff_seconds <= 0:
            raise ValueError(
                "idle_backoff_seconds must be greater than 0"
            )

        if self.stale_task_timeout_seconds <= 0:
            raise ValueError(
                "stale_task_timeout_seconds must be greater than 0"
            )


class AutoDevPipeline:
    """
    High-level autonomous AutoDev orchestration layer.

    Connects:
    - AutonomousTaskQueue,
    - AutoDevScheduler,
    - AutoDevWorker,
    - DeveloperController workflow.

    The pipeline exposes one public API for submitting,
    monitoring and controlling autonomous development tasks.
    """

    def __init__(
        self,
        *,
        policy: AutoDevPipelinePolicy | None = None,
        queue: AutonomousTaskQueue | None = None,
        scheduler: AutoDevScheduler | None = None,
    ) -> None:
        self.policy = policy or AutoDevPipelinePolicy()
        self.policy.validate()

        project_root = Path(
            self.policy.project_root
        ).resolve()

        queue_path = Path(
            self.policy.queue_storage_path
        )

        if not queue_path.is_absolute():
            queue_path = project_root / queue_path

        self.queue = queue or AutonomousTaskQueue(
            storage_path=queue_path,
            autosave=True,
        )

        scheduler_policy = SchedulerPolicy(
            poll_interval_seconds=(
                self.policy.poll_interval_seconds
            ),
            idle_backoff_seconds=(
                self.policy.idle_backoff_seconds
            ),
            max_parallel_tasks=(
                self.policy.max_parallel_tasks
            ),
            stale_task_timeout_seconds=(
                self.policy.stale_task_timeout_seconds
            ),
            recover_stale_tasks=True,
            autosave_queue=True,
        )

        self.scheduler = scheduler or AutoDevScheduler(
            self.queue,
            policy=scheduler_policy,
        )

        self._workers: dict[str, AutoDevWorker] = {}
        self._lock = threading.RLock()
        self._started_at: float | None = None
        self._last_error: str | None = None
        self._last_error_info: dict[str, Any] | None = None

        self._register_default_workers()

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    @property
    def last_error_info(
        self,
    ) -> dict[str, Any] | None:
        with self._lock:
            return (
                dict(self._last_error_info)
                if self._last_error_info
                else None
            )

    def _register_default_workers(self) -> None:
        with self._lock:
            if self._workers:
                return

            for index in range(self.policy.worker_count):
                worker_id = f"autodev-worker-{index + 1}"

                worker_policy = AutoDevWorkerPolicy(
                    project_root=self.policy.project_root,
                    auto_approve=self.policy.auto_approve,
                    auto_execute=self.policy.auto_execute,
                    auto_rollback=self.policy.auto_rollback,
                    require_safe_metadata=True,
                )

                worker = AutoDevWorker(
                    worker_id=worker_id,
                    policy=worker_policy,
                )

                self._workers[worker_id] = worker

                self.scheduler.register_worker(
                    worker_id=worker_id,
                    handler=worker.handle,
                    accepted_sources=None,
                    required_tags=None,
                    enabled=True,
                )

    def start(self) -> bool:
        with self._lock:
            try:
                started = self.scheduler.start()

                if started:
                    self._started_at = time.time()

                self._last_error = None
                self._last_error_info = None
                return started

            except Exception as exc:
                report = AutoDevErrorReporter.capture(
                    exc,
                    stage="autodev_pipeline.start",
                    context={
                        "scheduler_state": (
                            self.scheduler.state.value
                        ),
                    },
                    project_root=self.policy.project_root,
                )
                self._last_error = report.summary()
                self._last_error_info = report.as_dict()
                raise

    def stop(
        self,
        *,
        wait: bool = True,
        timeout: float | None = None,
    ) -> bool:
        with self._lock:
            try:
                stopped = self.scheduler.stop(
                    wait=wait,
                    timeout=timeout,
                )
                return stopped

            except Exception as exc:
                report = AutoDevErrorReporter.capture(
                    exc,
                    stage="autodev_pipeline.stop",
                    context={
                        "wait": wait,
                        "timeout": timeout,
                        "scheduler_state": (
                            self.scheduler.state.value
                        ),
                    },
                    project_root=self.policy.project_root,
                )
                self._last_error = report.summary()
                self._last_error_info = report.as_dict()
                raise

    def pause(self) -> bool:
        return self.scheduler.pause()

    def resume(self) -> bool:
        return self.scheduler.resume()

    def submit(self, *, title: str, description: str, source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, payload: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None, retry_policy: RetryPolicy | None=None, scheduled_for: float | None=None, timeout_seconds: float | None=None, reject_duplicates: bool=True) -> AutonomousTask:
        return _AUTODEV_PIPELINE_TASKS.submit(self, title=title, description=description, source=source, priority=priority, payload=payload, tags=tags, dependencies=dependencies, retry_policy=retry_policy, scheduled_for=scheduled_for, timeout_seconds=timeout_seconds, reject_duplicates=reject_duplicates)


    def submit_file_change(self, *, title: str, goal: str, path: str, proposed_content: str, target: str='', source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, auto_approve: bool | None=None, auto_execute: bool | None=None, auto_rollback: bool | None=None, metadata: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None) -> AutonomousTask:
        return _AUTODEV_PIPELINE_TASKS.submit_file_change(self, title=title, goal=goal, path=path, proposed_content=proposed_content, target=target, source=source, priority=priority, auto_approve=auto_approve, auto_execute=auto_execute, auto_rollback=auto_rollback, metadata=metadata, tags=tags, dependencies=dependencies)


    def submit_function_change(self, *, title: str, goal: str, path: str, function_name: str, new_function_code: str, target: str='', source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, auto_approve: bool | None=None, auto_execute: bool | None=None, auto_rollback: bool | None=None, metadata: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None) -> AutonomousTask:
        return _AUTODEV_PIPELINE_TASKS.submit_function_change(self, title=title, goal=goal, path=path, function_name=function_name, new_function_code=new_function_code, target=target, source=source, priority=priority, auto_approve=auto_approve, auto_execute=auto_execute, auto_rollback=auto_rollback, metadata=metadata, tags=tags, dependencies=dependencies)


    def submit_multi_file_change(self, *, title: str, goal: str, replacements: dict[str, str], target: str='', source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, auto_approve: bool | None=None, auto_execute: bool | None=None, auto_rollback: bool | None=None, metadata: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None) -> AutonomousTask:
        return _AUTODEV_PIPELINE_TASKS.submit_multi_file_change(self, title=title, goal=goal, replacements=replacements, target=target, source=source, priority=priority, auto_approve=auto_approve, auto_execute=auto_execute, auto_rollback=auto_rollback, metadata=metadata, tags=tags, dependencies=dependencies)


    def _apply_execution_flags(self, payload: dict[str, Any], *, auto_approve: bool | None, auto_execute: bool | None, auto_rollback: bool | None) -> None:
        return _AUTODEV_PIPELINE_TASKS._apply_execution_flags(self, payload, auto_approve=auto_approve, auto_execute=auto_execute, auto_rollback=auto_rollback)


    def approve_worker(
        self,
        worker_id: str,
        *,
        auto_execute: bool = True,
        auto_rollback: bool | None = None,
    ) -> dict[str, Any]:
        worker = self._require_worker(worker_id)
        result = worker.approve_current(
            auto_execute=auto_execute,
            auto_rollback=auto_rollback,
        )
        return result.to_dict()

    def reject_worker(
        self,
        worker_id: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        worker = self._require_worker(worker_id)
        result = worker.reject_current(reason)
        return result.to_dict()

    def rollback_worker(
        self,
        worker_id: str,
    ) -> dict[str, Any]:
        worker = self._require_worker(worker_id)
        result = worker.rollback_last()
        return result.to_dict()

    def _require_worker(
        self,
        worker_id: str,
    ) -> AutoDevWorker:
        with self._lock:
            worker = self._workers.get(worker_id)

            if worker is None:
                raise KeyError(
                    f"Unknown AutoDev worker: {worker_id}"
                )

            return worker

    def get_task(
        self,
        task_id: str,
    ) -> AutonomousTask | None:
        return self.queue.get(task_id)

    def cancel_task(
        self,
        task_id: str,
        *,
        reason: str = "Cancelled by AutoDevPipeline",
    ) -> AutonomousTask:
        return self.queue.cancel(
            task_id,
            reason=reason,
        )

    def retry_task(
        self,
        task_id: str,
        *,
        reset_attempts: bool = False,
    ) -> AutonomousTask:
        task = self.queue.retry_failed(
            task_id,
            reset_attempts=reset_attempts,
        )
        self.scheduler.wake()
        return task

    def list_tasks(
        self,
        *,
        statuses: Iterable[TaskStatus] | None = None,
        source: str | None = None,
        tag: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            task.to_dict()
            for task in self.queue.list_tasks(
                statuses=statuses,
                source=source,
                tag=tag,
                limit=limit,
            )
        ]

    def wait_for_task(self, task_id: str, *, timeout: float | None=None, poll_interval: float=0.25) -> AutonomousTask:
        return _AUTODEV_PIPELINE_TASKS.wait_for_task(self, task_id, timeout=timeout, poll_interval=poll_interval)


    def run_until_idle(self, *, timeout: float | None=None, poll_interval: float=0.25) -> bool:
        return _AUTODEV_PIPELINE_TASKS.run_until_idle(self, timeout=timeout, poll_interval=poll_interval)


    def workers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                worker.status()
                for worker in self._workers.values()
            ]

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self.scheduler.state.value,
                "started_at": self._started_at,
                "last_error": self._last_error,
                "last_error_info": (
                    dict(self._last_error_info)
                    if self._last_error_info
                    else None
                ),
                "policy": asdict(self.policy),
                "queue_metrics": (
                    self.queue.metrics().to_dict()
                ),
                "scheduler_metrics": (
                    self.scheduler.metrics().to_dict()
                ),
                "workers": self.workers(),
            }

    def snapshot(self) -> dict[str, Any]:
        return {
            "pipeline": self.status(),
            "scheduler": self.scheduler.snapshot(),
            "queue": self.queue.export_snapshot(),
        }

    def is_running(self) -> bool:
        return self.scheduler.is_running()

    def is_paused(self) -> bool:
        return self.scheduler.is_paused()

    def __enter__(self) -> AutoDevPipeline:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.stop(wait=True)

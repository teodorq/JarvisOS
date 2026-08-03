from __future__ import annotations

import time
from typing import Any, Iterable

from app.autodev.autodev_scheduler import SchedulerState
from app.autodev.autonomous_task_queue import (
    AutonomousTask,
    RetryPolicy,
    TaskPriority,
    TaskStatus,
)


class AutoDevPipelineTaskService:
    """Stateless task submission and waiting workflow."""

    def submit(self, pipeline: Any, *, title: str, description: str, source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, payload: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None, retry_policy: RetryPolicy | None=None, scheduled_for: float | None=None, timeout_seconds: float | None=None, reject_duplicates: bool=True) -> AutonomousTask:
        task = pipeline.queue.create_task(title=title, description=description, source=source, priority=priority, payload=payload, tags=tags, dependencies=dependencies, retry_policy=retry_policy, scheduled_for=scheduled_for, timeout_seconds=timeout_seconds, reject_duplicates=reject_duplicates)
        pipeline.scheduler.wake()
        return task

    def submit_file_change(self, pipeline: Any, *, title: str, goal: str, path: str, proposed_content: str, target: str='', source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, auto_approve: bool | None=None, auto_execute: bool | None=None, auto_rollback: bool | None=None, metadata: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None) -> AutonomousTask:
        payload = {'goal': goal, 'target': target or title, 'mode': 'file', 'path': path, 'proposed_content': proposed_content, 'metadata': dict(metadata or {})}
        pipeline._apply_execution_flags(payload, auto_approve=auto_approve, auto_execute=auto_execute, auto_rollback=auto_rollback)
        return pipeline.submit(title=title, description=goal, source=source, priority=priority, payload=payload, tags=tags, dependencies=dependencies)

    def submit_function_change(self, pipeline: Any, *, title: str, goal: str, path: str, function_name: str, new_function_code: str, target: str='', source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, auto_approve: bool | None=None, auto_execute: bool | None=None, auto_rollback: bool | None=None, metadata: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None) -> AutonomousTask:
        payload = {'goal': goal, 'target': target or title, 'mode': 'function', 'path': path, 'function_name': function_name, 'new_function_code': new_function_code, 'metadata': dict(metadata or {})}
        pipeline._apply_execution_flags(payload, auto_approve=auto_approve, auto_execute=auto_execute, auto_rollback=auto_rollback)
        return pipeline.submit(title=title, description=goal, source=source, priority=priority, payload=payload, tags=tags, dependencies=dependencies)

    def submit_multi_file_change(self, pipeline: Any, *, title: str, goal: str, replacements: dict[str, str], target: str='', source: str='autodev_pipeline', priority: TaskPriority=TaskPriority.NORMAL, auto_approve: bool | None=None, auto_execute: bool | None=None, auto_rollback: bool | None=None, metadata: dict[str, Any] | None=None, tags: Iterable[str] | None=None, dependencies: Iterable[str] | None=None) -> AutonomousTask:
        payload = {'goal': goal, 'target': target or title, 'mode': 'multi_file', 'replacements': dict(replacements), 'metadata': dict(metadata or {})}
        pipeline._apply_execution_flags(payload, auto_approve=auto_approve, auto_execute=auto_execute, auto_rollback=auto_rollback)
        return pipeline.submit(title=title, description=goal, source=source, priority=priority, payload=payload, tags=tags, dependencies=dependencies)

    def _apply_execution_flags(self, pipeline: Any, payload: dict[str, Any], *, auto_approve: bool | None, auto_execute: bool | None, auto_rollback: bool | None) -> None:
        if auto_approve is not None:
            payload['auto_approve'] = auto_approve
        if auto_execute is not None:
            payload['auto_execute'] = auto_execute
        if auto_rollback is not None:
            payload['auto_rollback'] = auto_rollback

    def wait_for_task(self, pipeline: Any, task_id: str, *, timeout: float | None=None, poll_interval: float=0.25) -> AutonomousTask:
        timeout, poll_interval = self._safe_wait_values(
            timeout,
            poll_interval,
        )
        deadline = None if timeout is None else time.time() + timeout
        while True:
            task = pipeline.queue.require(task_id)
            if task.is_terminal():
                return task
            if task.status == TaskStatus.COMPLETED or task.status == TaskStatus.FAILED or task.status == TaskStatus.CANCELLED:
                return task
            if deadline is not None and time.time() >= deadline:
                raise TimeoutError(f'Timeout while waiting for task {task_id}')
            time.sleep(poll_interval)

    def run_until_idle(self, pipeline: Any, *, timeout: float | None=None, poll_interval: float=0.25) -> bool:
        timeout, poll_interval = self._safe_wait_values(
            timeout,
            poll_interval,
        )
        if pipeline.scheduler.state == SchedulerState.STOPPED:
            pipeline.start()
        deadline = None if timeout is None else time.time() + timeout
        while True:
            metrics = pipeline.queue.metrics()
            unfinished = metrics.pending + metrics.ready + metrics.running + metrics.retry_wait + metrics.blocked
            if unfinished == 0:
                return True
            if deadline is not None and time.time() >= deadline:
                return False
            time.sleep(poll_interval)


    @staticmethod
    def _safe_wait_values(
        timeout: float | None,
        poll_interval: float,
    ) -> tuple[float | None, float]:
        try:
            interval = float(
                poll_interval
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "poll_interval must be a number"
            ) from error

        if (
            interval < 0.01
            or interval > 5.0
        ):
            raise ValueError(
                "poll_interval must be between 0.01 and 5 seconds"
            )

        if timeout is None:
            return None, interval

        try:
            safe_timeout = float(
                timeout
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "timeout must be a number"
            ) from error

        if (
            safe_timeout <= 0
            or safe_timeout > 86400
        ):
            raise ValueError(
                "timeout must be between 0 and 86400 seconds"
            )

        return safe_timeout, interval

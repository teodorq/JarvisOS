from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable


class TaskPriority(IntEnum):
    CRITICAL = 0
    HIGH = 10
    NORMAL = 20
    LOW = 30
    BACKGROUND = 40


class GoalStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 300.0

    def validate(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds cannot be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds cannot be negative")

    def delay_for_attempt(self, attempt_number: int) -> float:
        self.validate()
        if attempt_number <= 0:
            return 0.0

        delay = self.initial_delay_seconds * (
            self.backoff_multiplier ** max(0, attempt_number - 1)
        )
        return min(delay, self.max_delay_seconds)


@dataclass(slots=True)
class DevelopmentGoal:
    title: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: GoalStatus = GoalStatus.PLANNED
    task_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.description = self.description.strip()
        self.tags = sorted({
            str(tag).strip().lower()
            for tag in self.tags
            if str(tag).strip()
        })
        self.task_ids = list(dict.fromkeys(
            task_id for task_id in self.task_ids if task_id
        ))
        if not self.title:
            raise ValueError("Goal title cannot be empty")

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["priority"] = int(self.priority)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DevelopmentGoal:
        return cls(
            title=data["title"],
            description=data.get("description", ""),
            priority=TaskPriority(data.get("priority", TaskPriority.NORMAL)),
            tags=list(data.get("tags") or []),
            metadata=dict(data.get("metadata") or {}),
            goal_id=data.get("goal_id") or str(uuid.uuid4()),
            status=GoalStatus(data.get("status", GoalStatus.PLANNED)),
            task_ids=list(data.get("task_ids") or []),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            completed_at=data.get("completed_at"),
        )


@dataclass(slots=True)
class AutonomousTask:
    title: str
    description: str
    source: str = "unknown"
    priority: TaskPriority = TaskPriority.NORMAL
    payload: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    scheduled_for: float | None = None
    timeout_seconds: float | None = None
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    next_retry_at: float | None = None
    attempts: int = 0
    claimed_by: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.description = self.description.strip()
        self.source = self.source.strip() or "unknown"
        self.tags = sorted(
            {
                str(tag).strip().lower()
                for tag in self.tags
                if str(tag).strip()
            }
        )
        self.dependencies = list(
            dict.fromkeys(
                dependency
                for dependency in self.dependencies
                if dependency and dependency != self.task_id
            )
        )
        self.retry_policy.validate()

        if not self.title:
            raise ValueError("Task title cannot be empty")

        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")

        if not self.fingerprint:
            self.fingerprint = self.create_fingerprint()

    def create_fingerprint(self) -> str:
        normalized = {
            "title": self.title.casefold(),
            "description": self.description.casefold(),
            "source": self.source.casefold(),
            "payload": self.payload,
            "dependencies": sorted(self.dependencies),
        }
        serialized = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def touch(self) -> None:
        self.updated_at = time.time()

    def is_terminal(self) -> bool:
        return self.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["priority"] = int(self.priority)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomousTask:
        retry_data = data.get("retry_policy") or {}
        return cls(
            title=data["title"],
            description=data.get("description", ""),
            source=data.get("source", "unknown"),
            priority=TaskPriority(data.get("priority", TaskPriority.NORMAL)),
            payload=dict(data.get("payload") or {}),
            tags=list(data.get("tags") or []),
            dependencies=list(data.get("dependencies") or []),
            retry_policy=RetryPolicy(**retry_data),
            scheduled_for=data.get("scheduled_for"),
            timeout_seconds=data.get("timeout_seconds"),
            task_id=data.get("task_id") or str(uuid.uuid4()),
            status=TaskStatus(data.get("status", TaskStatus.PENDING)),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            next_retry_at=data.get("next_retry_at"),
            attempts=int(data.get("attempts", 0)),
            claimed_by=data.get("claimed_by"),
            result=data.get("result"),
            error=data.get("error"),
            fingerprint=data.get("fingerprint", ""),
        )


@dataclass(slots=True)
class QueueMetrics:
    total: int = 0
    pending: int = 0
    ready: int = 0
    running: int = 0
    retry_wait: int = 0
    blocked: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class AutonomousTaskQueue:
    """
    Thread-safe persistent task queue for autonomous JARVIS AutoDev work.

    The queue stores tasks in JSON and supports:
    - priorities,
    - dependencies,
    - scheduling,
    - retries,
    - duplicate protection,
    - worker claims,
    - cancellation,
    - persistent recovery,
    - metrics and filtering.
    """

    STORAGE_VERSION = 2
    DECISION_ENGINE_VERSION = "1.0.0"
    SUPPORTED_STORAGE_VERSIONS = {1, 2}

    def __init__(
        self,
        storage_path: str | Path = "data/autodev/autonomous_task_queue.json",
        *,
        autosave: bool = True,
        allow_duplicate_terminal_tasks: bool = True,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.autosave = autosave
        self.allow_duplicate_terminal_tasks = allow_duplicate_terminal_tasks
        self._tasks: dict[str, AutonomousTask] = {}
        self._goals: dict[str, DevelopmentGoal] = {}
        self._lock = threading.RLock()
        self._listeners: list[Callable[[str, AutonomousTask], None]] = []

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    def add_listener(
        self,
        listener: Callable[[str, AutonomousTask], None],
    ) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(
        self,
        listener: Callable[[str, AutonomousTask], None],
    ) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _emit(self, event_name: str, task: AutonomousTask) -> None:
        listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event_name, task)
            except Exception:
                continue

    def create_goal(
        self,
        title: str,
        description: str,
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        tags: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DevelopmentGoal:
        goal = DevelopmentGoal(
            title=title,
            description=description,
            priority=priority,
            tags=list(tags or []),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._goals[goal.goal_id] = goal
            self._save_if_enabled()
        return goal

    def get_goal(self, goal_id: str) -> DevelopmentGoal | None:
        with self._lock:
            return self._goals.get(goal_id)

    def require_goal(self, goal_id: str) -> DevelopmentGoal:
        goal = self.get_goal(goal_id)
        if goal is None:
            raise KeyError(f"Unknown goal id: {goal_id}")
        return goal

    def list_goals(
        self,
        *,
        statuses: Iterable[GoalStatus] | None = None,
    ) -> list[DevelopmentGoal]:
        with self._lock:
            goals = list(self._goals.values())
            if statuses is not None:
                allowed = set(statuses)
                goals = [goal for goal in goals if goal.status in allowed]
            goals.sort(key=lambda goal: (
                int(goal.priority),
                goal.created_at,
            ))
            return goals

    def add_task_to_goal(
        self,
        goal_id: str,
        task_id: str,
    ) -> DevelopmentGoal:
        with self._lock:
            goal = self.require_goal(goal_id)
            self.require(task_id)
            if task_id not in goal.task_ids:
                goal.task_ids.append(task_id)
                if goal.status == GoalStatus.PLANNED:
                    goal.status = GoalStatus.ACTIVE
                goal.touch()
                self._save_if_enabled()
            return goal

    def goal_progress(self, goal_id: str) -> dict[str, Any]:
        with self._lock:
            goal = self.require_goal(goal_id)
            tasks = [
                self._tasks[task_id]
                for task_id in goal.task_ids
                if task_id in self._tasks
            ]
            total = len(tasks)
            completed = sum(
                task.status == TaskStatus.COMPLETED for task in tasks
            )
            failed = sum(
                task.status == TaskStatus.FAILED for task in tasks
            )
            cancelled = sum(
                task.status == TaskStatus.CANCELLED for task in tasks
            )

            if total and completed == total:
                goal.status = GoalStatus.COMPLETED
                goal.completed_at = goal.completed_at or time.time()
                goal.touch()
            elif failed or cancelled:
                goal.status = GoalStatus.FAILED
                goal.touch()
            elif total:
                goal.status = GoalStatus.ACTIVE

            percent = 100.0 if total == 0 and goal.status == GoalStatus.COMPLETED else (
                round((completed / total) * 100.0, 2) if total else 0.0
            )
            return {
                "goal_id": goal.goal_id,
                "status": goal.status.value,
                "total_tasks": total,
                "completed_tasks": completed,
                "failed_tasks": failed,
                "cancelled_tasks": cancelled,
                "progress_percent": percent,
            }

    def set_goal_status(
        self,
        goal_id: str,
        status: GoalStatus,
    ) -> DevelopmentGoal:
        with self._lock:
            goal = self.require_goal(goal_id)
            goal.status = GoalStatus(status)
            goal.completed_at = (
                time.time()
                if goal.status == GoalStatus.COMPLETED
                else None
            )
            goal.touch()
            self._save_if_enabled()
            return goal

    def enqueue(
        self,
        task: AutonomousTask,
        *,
        reject_duplicates: bool = True,
    ) -> AutonomousTask:
        with self._lock:
            if task.task_id in self._tasks:
                raise ValueError(f"Task with id {task.task_id} already exists")

            if reject_duplicates:
                duplicate = self.find_duplicate(task)
                if duplicate is not None:
                    raise ValueError(
                        "Duplicate task detected: "
                        f"{duplicate.task_id} ({duplicate.status.value})"
                    )

            self._validate_dependencies(task)
            self._tasks[task.task_id] = task
            self._refresh_task_state(task)
            self._save_if_enabled()
            self._emit("task_enqueued", task)
            return task

    def create_task(
        self,
        title: str,
        description: str,
        *,
        source: str = "unknown",
        priority: TaskPriority = TaskPriority.NORMAL,
        payload: dict[str, Any] | None = None,
        tags: Iterable[str] | None = None,
        dependencies: Iterable[str] | None = None,
        retry_policy: RetryPolicy | None = None,
        scheduled_for: float | None = None,
        timeout_seconds: float | None = None,
        reject_duplicates: bool = True,
    ) -> AutonomousTask:
        task = AutonomousTask(
            title=title,
            description=description,
            source=source,
            priority=priority,
            payload=dict(payload or {}),
            tags=list(tags or []),
            dependencies=list(dependencies or []),
            retry_policy=retry_policy or RetryPolicy(),
            scheduled_for=scheduled_for,
            timeout_seconds=timeout_seconds,
        )
        return self.enqueue(task, reject_duplicates=reject_duplicates)

    def _validate_dependencies(self, task: AutonomousTask) -> None:
        missing = [
            dependency
            for dependency in task.dependencies
            if dependency not in self._tasks
        ]
        if missing:
            raise ValueError(
                "Task contains unknown dependencies: "
                + ", ".join(missing)
            )

        if self._would_create_cycle(task.task_id, task.dependencies):
            raise ValueError("Task dependency cycle detected")

    def _would_create_cycle(
        self,
        task_id: str,
        dependencies: Iterable[str],
    ) -> bool:
        graph: dict[str, list[str]] = {
            existing_id: list(existing.dependencies)
            for existing_id, existing in self._tasks.items()
        }
        graph[task_id] = list(dependencies)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False

            visiting.add(node)
            for dependency in graph.get(node, []):
                if visit(dependency):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return visit(task_id)

    def find_duplicate(
        self,
        task: AutonomousTask,
    ) -> AutonomousTask | None:
        for existing in self._tasks.values():
            if existing.fingerprint != task.fingerprint:
                continue

            if (
                self.allow_duplicate_terminal_tasks
                and existing.is_terminal()
            ):
                continue

            return existing
        return None

    def get(self, task_id: str) -> AutonomousTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def require(self, task_id: str) -> AutonomousTask:
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task id: {task_id}")
        return task

    def list_tasks(
        self,
        *,
        statuses: Iterable[TaskStatus] | None = None,
        source: str | None = None,
        tag: str | None = None,
        limit: int | None = None,
    ) -> list[AutonomousTask]:
        with self._lock:
            self.refresh()
            tasks = list(self._tasks.values())

            if statuses is not None:
                status_set = set(statuses)
                tasks = [
                    task
                    for task in tasks
                    if task.status in status_set
                ]

            if source is not None:
                tasks = [
                    task
                    for task in tasks
                    if task.source == source
                ]

            if tag is not None:
                normalized_tag = tag.strip().lower()
                tasks = [
                    task
                    for task in tasks
                    if normalized_tag in task.tags
                ]

            tasks.sort(
                key=lambda task: (
                    int(task.priority),
                    task.scheduled_for or 0.0,
                    task.created_at,
                )
            )

            if limit is not None:
                tasks = tasks[: max(0, limit)]

            return tasks

    def refresh(self) -> None:
        with self._lock:
            changed = False
            for task in self._tasks.values():
                old_status = task.status
                self._refresh_task_state(task)
                if old_status != task.status:
                    changed = True
                    self._emit("task_status_changed", task)

            if changed:
                self._save_if_enabled()

    def _refresh_task_state(self, task: AutonomousTask) -> None:
        if task.is_terminal() or task.status == TaskStatus.RUNNING:
            return

        now = time.time()

        if task.status == TaskStatus.RETRY_WAIT:
            if task.next_retry_at is not None and now < task.next_retry_at:
                return
            task.next_retry_at = None

        if task.scheduled_for is not None and now < task.scheduled_for:
            task.status = TaskStatus.PENDING
            task.touch()
            return

        dependency_states = [
            self._tasks[dependency].status
            for dependency in task.dependencies
            if dependency in self._tasks
        ]

        if any(
            state in {TaskStatus.FAILED, TaskStatus.CANCELLED}
            for state in dependency_states
        ):
            task.status = TaskStatus.BLOCKED
            task.error = "Dependency failed or was cancelled"
            task.touch()
            return

        if any(
            state != TaskStatus.COMPLETED
            for state in dependency_states
        ):
            task.status = TaskStatus.BLOCKED
            task.touch()
            return

        task.status = TaskStatus.READY
        task.touch()

    def decision_score(
        self,
        task: AutonomousTask,
    ) -> float:
        with self._lock:
            self._refresh_task_state(task)

            if task.status != TaskStatus.READY:
                return float("-inf")

            priority_points = {
                TaskPriority.CRITICAL: 100.0,
                TaskPriority.HIGH: 75.0,
                TaskPriority.NORMAL: 50.0,
                TaskPriority.LOW: 25.0,
                TaskPriority.BACKGROUND: 10.0,
            }[task.priority]

            payload = (
                task.payload
                if isinstance(task.payload, dict)
                else {}
            )

            impact = self._bounded_number(
                payload.get(
                    "impact_score",
                    payload.get("impact", 50.0),
                ),
                default=50.0,
                minimum=0.0,
                maximum=100.0,
            )
            risk = self._bounded_number(
                payload.get(
                    "risk_score",
                    payload.get("risk", 50.0),
                ),
                default=50.0,
                minimum=0.0,
                maximum=100.0,
            )
            confidence = self._bounded_number(
                payload.get("confidence", 0.5),
                default=0.5,
                minimum=0.0,
                maximum=1.0,
            )

            unlocked_dependents = sum(
                1
                for candidate in self._tasks.values()
                if task.task_id in candidate.dependencies
                and not candidate.is_terminal()
            )

            age_hours = max(
                0.0,
                (time.time() - task.created_at) / 3600.0,
            )

            return round(
                priority_points
                + impact * 0.45
                + confidence * 15.0
                + min(25.0, unlocked_dependents * 5.0)
                + min(10.0, age_hours * 0.5)
                - risk * 0.35
                - task.attempts * 8.0,
                3,
            )

    def ranked_ready_tasks(
        self,
        *,
        accepted_sources: Iterable[str] | None = None,
        required_tags: Iterable[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        with self._lock:
            self.refresh()

            source_filter = (
                set(accepted_sources)
                if accepted_sources is not None
                else None
            )
            required_tag_set = {
                str(tag).strip().lower()
                for tag in (required_tags or [])
                if str(tag).strip()
            }

            ranked: list[tuple[float, AutonomousTask]] = []

            for task in self._tasks.values():
                if task.status != TaskStatus.READY:
                    continue
                if (
                    source_filter is not None
                    and task.source not in source_filter
                ):
                    continue
                if (
                    required_tag_set
                    and not required_tag_set.issubset(
                        set(task.tags)
                    )
                ):
                    continue

                ranked.append(
                    (self.decision_score(task), task)
                )

            ranked.sort(
                key=lambda item: (
                    -item[0],
                    int(item[1].priority),
                    item[1].created_at,
                )
            )

            return [
                {
                    "rank": index,
                    "decision_score": score,
                    "task": task.to_dict(),
                }
                for index, (score, task) in enumerate(
                    ranked[:max(0, int(limit))],
                    start=1,
                )
            ]

    @staticmethod
    def _bounded_number(
        value: Any,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            normalized = default

        return max(minimum, min(maximum, normalized))

    def claim_next(
        self,
        worker_id: str,
        *,
        accepted_sources: Iterable[str] | None = None,
        required_tags: Iterable[str] | None = None,
    ) -> AutonomousTask | None:
        worker_id = worker_id.strip()
        if not worker_id:
            raise ValueError("worker_id cannot be empty")

        with self._lock:
            self.refresh()

            source_filter = (
                set(accepted_sources)
                if accepted_sources is not None
                else None
            )
            required_tag_set = {
                tag.strip().lower()
                for tag in (required_tags or [])
                if tag.strip()
            }

            candidates = []
            for task in self._tasks.values():
                if task.status != TaskStatus.READY:
                    continue
                if source_filter is not None and task.source not in source_filter:
                    continue
                if required_tag_set and not required_tag_set.issubset(
                    set(task.tags)
                ):
                    continue
                candidates.append(task)

            candidates.sort(
                key=lambda task: (
                    -self.decision_score(task),
                    int(task.priority),
                    task.scheduled_for or 0.0,
                    task.created_at,
                )
            )

            if not candidates:
                return None

            task = candidates[0]
            task.status = TaskStatus.RUNNING
            task.claimed_by = worker_id
            task.started_at = time.time()
            task.attempts += 1
            task.error = None
            task.touch()

            self._save_if_enabled()
            self._emit("task_claimed", task)
            return task

    def complete(
        self,
        task_id: str,
        *,
        result: dict[str, Any] | None = None,
        worker_id: str | None = None,
    ) -> AutonomousTask:
        with self._lock:
            task = self.require(task_id)
            self._validate_worker_claim(task, worker_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Task {task_id} is not running"
                )

            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = dict(result or {})
            task.error = None
            task.claimed_by = None
            task.touch()

            self._refresh_dependents(task.task_id)
            self._save_if_enabled()
            self._emit("task_completed", task)
            return task

    def fail(
        self,
        task_id: str,
        error: str,
        *,
        worker_id: str | None = None,
        retryable: bool = True,
    ) -> AutonomousTask:
        with self._lock:
            task = self.require(task_id)
            self._validate_worker_claim(task, worker_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Task {task_id} is not running"
                )

            task.error = error.strip() or "Unknown task error"
            task.claimed_by = None
            task.touch()

            can_retry = (
                retryable
                and task.attempts < task.retry_policy.max_attempts
            )

            if can_retry:
                delay = task.retry_policy.delay_for_attempt(task.attempts)
                task.next_retry_at = time.time() + delay
                task.status = TaskStatus.RETRY_WAIT
                task.started_at = None
                self._emit("task_retry_scheduled", task)
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                self._refresh_dependents(task.task_id)
                self._emit("task_failed", task)

            self._save_if_enabled()
            return task

    def release(
        self,
        task_id: str,
        *,
        worker_id: str | None = None,
    ) -> AutonomousTask:
        with self._lock:
            task = self.require(task_id)
            self._validate_worker_claim(task, worker_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Task {task_id} is not running"
                )

            task.status = TaskStatus.PENDING
            task.claimed_by = None
            task.started_at = None
            task.touch()
            self._refresh_task_state(task)

            self._save_if_enabled()
            self._emit("task_released", task)
            return task

    def cancel(
        self,
        task_id: str,
        *,
        reason: str = "Cancelled",
    ) -> AutonomousTask:
        with self._lock:
            task = self.require(task_id)

            if task.is_terminal():
                return task

            task.status = TaskStatus.CANCELLED
            task.error = reason
            task.completed_at = time.time()
            task.claimed_by = None
            task.touch()

            self._refresh_dependents(task.task_id)
            self._save_if_enabled()
            self._emit("task_cancelled", task)
            return task

    def retry_failed(
        self,
        task_id: str,
        *,
        reset_attempts: bool = False,
    ) -> AutonomousTask:
        with self._lock:
            task = self.require(task_id)

            if task.status != TaskStatus.FAILED:
                raise ValueError(
                    f"Task {task_id} is not failed"
                )

            task.status = TaskStatus.PENDING
            task.completed_at = None
            task.next_retry_at = None
            task.error = None
            task.claimed_by = None
            task.started_at = None

            if reset_attempts:
                task.attempts = 0

            task.touch()
            self._refresh_task_state(task)

            self._save_if_enabled()
            self._emit("task_requeued", task)
            return task

    def update_priority(
        self,
        task_id: str,
        priority: TaskPriority,
    ) -> AutonomousTask:
        with self._lock:
            task = self.require(task_id)
            task.priority = priority
            task.touch()
            self._save_if_enabled()
            self._emit("task_priority_changed", task)
            return task

    def _validate_worker_claim(
        self,
        task: AutonomousTask,
        worker_id: str | None,
    ) -> None:
        if worker_id is None:
            return

        if task.claimed_by != worker_id:
            raise PermissionError(
                f"Task {task.task_id} is claimed by "
                f"{task.claimed_by!r}, not {worker_id!r}"
            )

    def _refresh_dependents(self, dependency_id: str) -> None:
        for task in self._tasks.values():
            if dependency_id in task.dependencies:
                self._refresh_task_state(task)

    def recover_running_tasks(
        self,
        *,
        reason: str = "Recovered after process restart",
    ) -> int:
        with self._lock:
            recovered = 0
            for task in self._tasks.values():
                if task.status != TaskStatus.RUNNING:
                    continue

                task.status = TaskStatus.PENDING
                task.claimed_by = None
                task.started_at = None
                task.error = reason
                task.touch()
                self._refresh_task_state(task)
                recovered += 1

            if recovered:
                self._save_if_enabled()

            return recovered

    def purge_terminal(
        self,
        *,
        older_than_seconds: float = 0.0,
    ) -> int:
        if older_than_seconds < 0:
            raise ValueError(
                "older_than_seconds cannot be negative"
            )

        with self._lock:
            threshold = time.time() - older_than_seconds
            removable = [
                task_id
                for task_id, task in self._tasks.items()
                if task.is_terminal()
                and (task.completed_at or task.updated_at) <= threshold
                and not self._has_dependents(task_id)
            ]

            for task_id in removable:
                del self._tasks[task_id]

            if removable:
                self._save_if_enabled()

            return len(removable)

    def _has_dependents(self, task_id: str) -> bool:
        return any(
            task_id in task.dependencies
            for task in self._tasks.values()
        )

    def metrics(self) -> QueueMetrics:
        with self._lock:
            self.refresh()
            metrics = QueueMetrics(total=len(self._tasks))

            for task in self._tasks.values():
                if task.status == TaskStatus.PENDING:
                    metrics.pending += 1
                elif task.status == TaskStatus.READY:
                    metrics.ready += 1
                elif task.status == TaskStatus.RUNNING:
                    metrics.running += 1
                elif task.status == TaskStatus.RETRY_WAIT:
                    metrics.retry_wait += 1
                elif task.status == TaskStatus.BLOCKED:
                    metrics.blocked += 1
                elif task.status == TaskStatus.COMPLETED:
                    metrics.completed += 1
                elif task.status == TaskStatus.FAILED:
                    metrics.failed += 1
                elif task.status == TaskStatus.CANCELLED:
                    metrics.cancelled += 1

            return metrics

    def save(self) -> None:
        with self._lock:
            payload = {
                "version": self.STORAGE_VERSION,
                "saved_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "tasks": [
                    task.to_dict()
                    for task in self._tasks.values()
                ],
                "goals": [
                    goal.to_dict()
                    for goal in self._goals.values()
                ],
            }

            temporary_path = self.storage_path.with_suffix(
                self.storage_path.suffix + ".tmp"
            )

            temporary_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=str,
                ),
                encoding="utf-8",
            )
            temporary_path.replace(self.storage_path)

    def _save_if_enabled(self) -> None:
        if self.autosave:
            self.save()

    def load(self) -> None:
        with self._lock:
            if not self.storage_path.exists():
                return

            raw = self.storage_path.read_text(encoding="utf-8")
            if not raw.strip():
                return

            payload = json.loads(raw)
            version = int(payload.get("version", 0))

            if version not in self.SUPPORTED_STORAGE_VERSIONS:
                raise ValueError(
                    "Unsupported queue storage version: "
                    f"{version}"
                )

            loaded_tasks: dict[str, AutonomousTask] = {}
            for task_data in payload.get("tasks", []):
                task = AutonomousTask.from_dict(task_data)
                loaded_tasks[task.task_id] = task

            loaded_goals: dict[str, DevelopmentGoal] = {}
            for goal_data in payload.get("goals", []):
                goal = DevelopmentGoal.from_dict(goal_data)
                loaded_goals[goal.goal_id] = goal

            self._tasks = loaded_tasks
            self._goals = loaded_goals
            self.recover_running_tasks()

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            self.refresh()
            return {
                "storage_version": self.STORAGE_VERSION,
                "metrics": self.metrics().to_dict(),
                "tasks": [
                    task.to_dict()
                    for task in self.list_tasks()
                ],
                "goals": [
                    goal.to_dict()
                    for goal in self.list_goals()
                ],
            }

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._goals.clear()
            self._save_if_enabled()

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)

    def __contains__(self, task_id: object) -> bool:
        with self._lock:
            return task_id in self._tasks

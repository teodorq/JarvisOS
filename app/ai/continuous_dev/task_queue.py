"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import heapq
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class TaskQueueStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskQueuePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DevelopmentTaskType(str, Enum):
    ANALYZE = "ANALYZE"
    RESEARCH = "RESEARCH"
    REASON = "REASON"
    PLAN = "PLAN"
    PREPARE_PATCH = "PREPARE_PATCH"
    APPROVE = "APPROVE"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    ROLLBACK = "ROLLBACK"
    REPORT = "REPORT"
    UNKNOWN = "UNKNOWN"


@dataclass
class DevelopmentTask:
    task_id: str
    cycle_id: str
    title: str
    description: str
    task_type: str
    priority: str
    priority_score: float
    status: str
    order: int
    dependencies: list[str]
    blockers: list[str]
    attempts: int
    max_attempts: int
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    errors: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskQueue:

    PRIORITY_SCORES = {
        TaskQueuePriority.LOW.value: 20.0,
        TaskQueuePriority.MEDIUM.value: 45.0,
        TaskQueuePriority.HIGH.value: 70.0,
        TaskQueuePriority.CRITICAL.value: 95.0,
    }

    TERMINAL_STATUSES = {
        TaskQueueStatus.COMPLETED.value,
        TaskQueueStatus.FAILED.value,
        TaskQueueStatus.CANCELLED.value,
    }

    def __init__(
        self,
        storage_path: str | Path = (
            "data/continuous_dev/task_queue.json"
        ),
        auto_save: bool = True,
    ) -> None:

        self.storage_path = Path(storage_path)
        self.auto_save = bool(auto_save)

        self._tasks: dict[
            str,
            DevelopmentTask,
        ] = {}

        self._ensure_storage()
        self.load()

    def add_task(
        self,
        cycle_id: str,
        title: str,
        description: str = "",
        task_type: str = DevelopmentTaskType.UNKNOWN.value,
        priority: str = TaskQueuePriority.MEDIUM.value,
        order: int | None = None,
        dependencies: list[str] | None = None,
        blockers: list[str] | None = None,
        max_attempts: int = 3,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_cycle_id = str(cycle_id).strip()
        normalized_title = str(title).strip()

        if not normalized_cycle_id:
            raise ValueError(
                "TaskQueue wymaga cycle_id."
            )

        if not normalized_title:
            raise ValueError(
                "TaskQueue wymaga tytułu zadania."
            )

        normalized_priority = self._normalize_enum_value(
            priority,
            TaskQueuePriority,
            TaskQueuePriority.MEDIUM.value,
        )

        normalized_type = self._normalize_enum_value(
            task_type,
            DevelopmentTaskType,
            DevelopmentTaskType.UNKNOWN.value,
        )

        normalized_dependencies = self._safe_string_list(
            dependencies or []
        )

        normalized_order = (
            int(order)
            if order is not None
            else len(self._tasks) + 1
        )

        now = self._utc_now()

        task = DevelopmentTask(
            task_id=f"development_task_{uuid4().hex}",
            cycle_id=normalized_cycle_id,
            title=normalized_title,
            description=str(description).strip(),
            task_type=normalized_type,
            priority=normalized_priority,
            priority_score=self.PRIORITY_SCORES[
                normalized_priority
            ],
            status=TaskQueueStatus.PENDING.value,
            order=max(
                1,
                normalized_order,
            ),
            dependencies=normalized_dependencies,
            blockers=self._safe_string_list(
                blockers or []
            ),
            attempts=0,
            max_attempts=max(
                1,
                int(max_attempts),
            ),
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
            input_data=self._safe_dict(
                input_data
            ),
            output_data={},
            errors=[],
            metadata={
                "task_queue_version": "1.0.0",
                **(metadata or {}),
            },
        )

        self._tasks[
            task.task_id
        ] = task

        self._refresh_states()
        self._save_if_enabled()

        return task.to_dict()

    def enqueue(
        self,
        cycle_id: str,
        title: str,
        description: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:

        return self.add_task(
            cycle_id=cycle_id,
            title=title,
            description=description,
            **kwargs,
        )

    def add_tasks(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        result: list[
            dict[str, Any]
        ] = []

        for item in tasks:
            if not isinstance(
                item,
                dict,
            ):
                continue

            result.append(
                self.add_task(
                    cycle_id=str(
                        item.get(
                            "cycle_id",
                            "",
                        )
                    ),
                    title=str(
                        item.get(
                            "title",
                            "",
                        )
                    ),
                    description=str(
                        item.get(
                            "description",
                            "",
                        )
                    ),
                    task_type=str(
                        item.get(
                            "task_type",
                            DevelopmentTaskType.UNKNOWN.value,
                        )
                    ),
                    priority=str(
                        item.get(
                            "priority",
                            TaskQueuePriority.MEDIUM.value,
                        )
                    ),
                    order=item.get(
                        "order"
                    ),
                    dependencies=self._safe_string_list(
                        item.get(
                            "dependencies",
                            [],
                        )
                    ),
                    blockers=self._safe_string_list(
                        item.get(
                            "blockers",
                            [],
                        )
                    ),
                    max_attempts=self._safe_int(
                        item.get(
                            "max_attempts",
                            3,
                        ),
                        3,
                    ),
                    input_data=self._safe_dict(
                        item.get(
                            "input_data",
                            {},
                        )
                    ),
                    metadata=self._safe_dict(
                        item.get(
                            "metadata",
                            {},
                        )
                    ),
                )
            )

        return result

    def next_task(
        self,
        cycle_id: str | None = None,
    ) -> dict[str, Any] | None:

        self._refresh_states()

        heap: list[
            tuple[
                float,
                int,
                str,
            ]
        ] = []

        for task in self._tasks.values():
            if (
                cycle_id is not None
                and task.cycle_id
                != str(cycle_id).strip()
            ):
                continue

            if task.status != TaskQueueStatus.READY.value:
                continue

            heapq.heappush(
                heap,
                (
                    -task.priority_score,
                    task.order,
                    task.task_id,
                ),
            )

        if not heap:
            return None

        _, _, task_id = heapq.heappop(
            heap
        )

        return self._tasks[
            task_id
        ].to_dict()

    def start_task(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        self._refresh_states()

        if task.status not in {
            TaskQueueStatus.READY.value,
            TaskQueueStatus.PENDING.value,
            TaskQueueStatus.BLOCKED.value,
        }:
            return task.to_dict()

        if not self._dependencies_completed(
            task
        ):
            task.status = TaskQueueStatus.BLOCKED.value
            task.updated_at = self._utc_now()
            self._save_if_enabled()
            return task.to_dict()

        if task.blockers:
            task.status = TaskQueueStatus.BLOCKED.value
            task.updated_at = self._utc_now()
            self._save_if_enabled()
            return task.to_dict()

        task.status = TaskQueueStatus.RUNNING.value
        task.attempts += 1
        task.started_at = (
            task.started_at
            or self._utc_now()
        )
        task.updated_at = self._utc_now()

        self._save_if_enabled()
        return task.to_dict()

    def complete_task(
        self,
        task_id: str,
        output_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        task.status = TaskQueueStatus.COMPLETED.value
        task.completed_at = self._utc_now()
        task.updated_at = task.completed_at
        task.output_data = self._safe_dict(
            output_data
        )

        self._refresh_states()
        self._save_if_enabled()

        return task.to_dict()

    def fail_task(
        self,
        task_id: str,
        error: str,
        output_data: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        normalized_error = str(
            error
        ).strip()

        if normalized_error:
            task.errors = self._unique_strings(
                task.errors
                + [normalized_error]
            )

        task.output_data = self._safe_dict(
            output_data
        )

        if (
            retry
            and task.attempts
            < task.max_attempts
        ):
            task.status = TaskQueueStatus.READY.value
            task.started_at = None

        else:
            task.status = TaskQueueStatus.FAILED.value
            task.completed_at = self._utc_now()

        task.updated_at = self._utc_now()

        self._refresh_states()
        self._save_if_enabled()

        return task.to_dict()

    def cancel_task(
        self,
        task_id: str,
        reason: str | None = None,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        task.status = TaskQueueStatus.CANCELLED.value
        task.completed_at = self._utc_now()
        task.updated_at = task.completed_at

        if reason:
            task.errors = self._unique_strings(
                task.errors
                + [
                    f"Anulowano: {reason}"
                ]
            )

        self._refresh_states()
        self._save_if_enabled()

        return task.to_dict()

    def add_blocker(
        self,
        task_id: str,
        blocker: str,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        normalized_blocker = str(
            blocker
        ).strip()

        if normalized_blocker:
            task.blockers = self._unique_strings(
                task.blockers
                + [normalized_blocker]
            )

        task.status = TaskQueueStatus.BLOCKED.value
        task.updated_at = self._utc_now()

        self._save_if_enabled()
        return task.to_dict()

    def remove_blocker(
        self,
        task_id: str,
        blocker: str | None = None,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        if blocker is None:
            task.blockers = []

        else:
            normalized = str(
                blocker
            ).strip().lower()

            task.blockers = [
                item
                for item in task.blockers
                if item.lower()
                != normalized
            ]

        task.updated_at = self._utc_now()

        self._refresh_states()
        self._save_if_enabled()

        return task.to_dict()

    def reprioritize(
        self,
        task_id: str,
        priority: str,
        manual_score: float | None = None,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        normalized_priority = self._normalize_enum_value(
            priority,
            TaskQueuePriority,
            task.priority,
        )

        task.priority = normalized_priority
        task.priority_score = (
            float(manual_score)
            if manual_score is not None
            else self.PRIORITY_SCORES[
                normalized_priority
            ]
        )

        task.priority_score = max(
            0.0,
            min(
                100.0,
                task.priority_score,
            ),
        )

        task.updated_at = self._utc_now()
        self._save_if_enabled()

        return task.to_dict()

    def get_task(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:

        task = self._get_task(
            task_id
        )

        if task is None:
            return None

        return task.to_dict()

    def list_tasks(
        self,
        cycle_id: str | None = None,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:

        self._refresh_states()

        normalized_cycle_id = (
            str(cycle_id).strip()
            if cycle_id is not None
            else None
        )

        normalized_status = (
            str(status).strip().upper()
            if status is not None
            else None
        )

        normalized_task_type = (
            str(task_type).strip().upper()
            if task_type is not None
            else None
        )

        tasks = list(
            self._tasks.values()
        )

        tasks.sort(
            key=lambda task: (
                -task.priority_score,
                task.order,
                task.created_at,
            )
        )

        result: list[
            dict[str, Any]
        ] = []

        for task in tasks:
            if (
                normalized_cycle_id
                and task.cycle_id
                != normalized_cycle_id
            ):
                continue

            if (
                normalized_status
                and task.status
                != normalized_status
            ):
                continue

            if (
                normalized_task_type
                and task.task_type
                != normalized_task_type
            ):
                continue

            result.append(
                task.to_dict()
            )

            if len(result) >= max(
                1,
                int(limit),
            ):
                break

        return result

    def ready_tasks(
        self,
        cycle_id: str | None = None,
    ) -> list[dict[str, Any]]:

        return self.list_tasks(
            cycle_id=cycle_id,
            status=TaskQueueStatus.READY.value,
        )

    def blocked_tasks(
        self,
        cycle_id: str | None = None,
    ) -> list[dict[str, Any]]:

        return self.list_tasks(
            cycle_id=cycle_id,
            status=TaskQueueStatus.BLOCKED.value,
        )

    def completed_tasks(
        self,
        cycle_id: str | None = None,
    ) -> list[dict[str, Any]]:

        return self.list_tasks(
            cycle_id=cycle_id,
            status=TaskQueueStatus.COMPLETED.value,
        )

    def has_pending_work(
        self,
        cycle_id: str | None = None,
    ) -> bool:

        for task in self._tasks.values():
            if (
                cycle_id is not None
                and task.cycle_id
                != str(cycle_id).strip()
            ):
                continue

            if task.status not in self.TERMINAL_STATUSES:
                return True

        return False

    def is_cycle_complete(
        self,
        cycle_id: str,
    ) -> bool:

        cycle_tasks = [
            task
            for task in self._tasks.values()
            if task.cycle_id
            == str(cycle_id).strip()
        ]

        if not cycle_tasks:
            return False

        return all(
            task.status
            in {
                TaskQueueStatus.COMPLETED.value,
                TaskQueueStatus.CANCELLED.value,
            }
            for task in cycle_tasks
        )

    def summary(
        self,
        cycle_id: str | None = None,
    ) -> dict[str, Any]:

        status_counts = {
            status.value: 0
            for status in TaskQueueStatus
        }

        selected_tasks = [
            task
            for task in self._tasks.values()
            if (
                cycle_id is None
                or task.cycle_id
                == str(cycle_id).strip()
            )
        ]

        for task in selected_tasks:
            status_counts[
                task.status
            ] = status_counts.get(
                task.status,
                0,
            ) + 1

        return {
            "tasks_count": len(
                selected_tasks
            ),
            "ready_count": status_counts.get(
                TaskQueueStatus.READY.value,
                0,
            ),
            "running_count": status_counts.get(
                TaskQueueStatus.RUNNING.value,
                0,
            ),
            "blocked_count": status_counts.get(
                TaskQueueStatus.BLOCKED.value,
                0,
            ),
            "completed_count": status_counts.get(
                TaskQueueStatus.COMPLETED.value,
                0,
            ),
            "failed_count": status_counts.get(
                TaskQueueStatus.FAILED.value,
                0,
            ),
            "status_counts": status_counts,
            "cycle_id": cycle_id,
            "queue_version": "1.0.0",
            "storage_path": str(
                self.storage_path
            ),
        }

    def save(
        self,
    ) -> None:

        self._ensure_storage()

        payload = {
            "version": "1.0.0",
            "saved_at": self._utc_now(),
            "tasks": [
                task.to_dict()
                for task in self._tasks.values()
            ],
        }

        temporary_path = (
            self.storage_path.with_suffix(
                self.storage_path.suffix
                + ".tmp"
            )
        )

        temporary_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(
            self.storage_path
        )

    def load(
        self,
    ) -> None:

        if not self.storage_path.exists():
            self._tasks = {}
            return

        try:
            raw_text = self.storage_path.read_text(
                encoding="utf-8"
            )

            if not raw_text.strip():
                self._tasks = {}
                return

            payload = json.loads(
                raw_text
            )

            raw_tasks = payload.get(
                "tasks",
                [],
            )

            loaded: dict[
                str,
                DevelopmentTask,
            ] = {}

            if isinstance(
                raw_tasks,
                list,
            ):
                for raw_task in raw_tasks:
                    if not isinstance(
                        raw_task,
                        dict,
                    ):
                        continue

                    try:
                        task = self._task_from_dict(
                            raw_task
                        )

                        loaded[
                            task.task_id
                        ] = task

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

            self._tasks = loaded
            self._refresh_states()

        except (
            OSError,
            json.JSONDecodeError,
        ):
            self._tasks = {}

    def clear(
        self,
        cycle_id: str | None = None,
    ) -> None:

        if cycle_id is None:
            self._tasks = {}

        else:
            normalized_cycle_id = str(
                cycle_id
            ).strip()

            self._tasks = {
                task_id: task
                for task_id, task
                in self._tasks.items()
                if task.cycle_id
                != normalized_cycle_id
            }

        self._save_if_enabled()

    def _refresh_states(
        self,
    ) -> None:

        for task in self._tasks.values():
            if task.status in self.TERMINAL_STATUSES:
                continue

            if task.status == TaskQueueStatus.RUNNING.value:
                continue

            if task.blockers:
                task.status = TaskQueueStatus.BLOCKED.value
                continue

            if self._dependencies_completed(
                task
            ):
                task.status = TaskQueueStatus.READY.value

            else:
                task.status = TaskQueueStatus.BLOCKED.value

    def _dependencies_completed(
        self,
        task: DevelopmentTask,
    ) -> bool:

        for dependency_id in task.dependencies:
            dependency = self._tasks.get(
                dependency_id
            )

            if dependency is None:
                return False

            if dependency.status != TaskQueueStatus.COMPLETED.value:
                return False

        return True

    def _task_from_dict(
        self,
        data: dict[str, Any],
    ) -> DevelopmentTask:

        return DevelopmentTask(
            task_id=str(
                data.get(
                    "task_id",
                    f"development_task_{uuid4().hex}",
                )
            ),
            cycle_id=str(
                data.get(
                    "cycle_id",
                    "",
                )
            ),
            title=str(
                data.get(
                    "title",
                    "Nieznane zadanie",
                )
            ),
            description=str(
                data.get(
                    "description",
                    "",
                )
            ),
            task_type=self._normalize_enum_value(
                data.get(
                    "task_type",
                    DevelopmentTaskType.UNKNOWN.value,
                ),
                DevelopmentTaskType,
                DevelopmentTaskType.UNKNOWN.value,
            ),
            priority=self._normalize_enum_value(
                data.get(
                    "priority",
                    TaskQueuePriority.MEDIUM.value,
                ),
                TaskQueuePriority,
                TaskQueuePriority.MEDIUM.value,
            ),
            priority_score=max(
                0.0,
                min(
                    100.0,
                    self._safe_float(
                        data.get(
                            "priority_score",
                            45.0,
                        ),
                        45.0,
                    ),
                ),
            ),
            status=self._normalize_enum_value(
                data.get(
                    "status",
                    TaskQueueStatus.PENDING.value,
                ),
                TaskQueueStatus,
                TaskQueueStatus.PENDING.value,
            ),
            order=max(
                1,
                self._safe_int(
                    data.get(
                        "order",
                        1,
                    ),
                    1,
                ),
            ),
            dependencies=self._safe_string_list(
                data.get(
                    "dependencies",
                    [],
                )
            ),
            blockers=self._safe_string_list(
                data.get(
                    "blockers",
                    [],
                )
            ),
            attempts=max(
                0,
                self._safe_int(
                    data.get(
                        "attempts",
                        0,
                    ),
                    0,
                ),
            ),
            max_attempts=max(
                1,
                self._safe_int(
                    data.get(
                        "max_attempts",
                        3,
                    ),
                    3,
                ),
            ),
            created_at=str(
                data.get(
                    "created_at",
                    self._utc_now(),
                )
            ),
            updated_at=str(
                data.get(
                    "updated_at",
                    self._utc_now(),
                )
            ),
            started_at=self._optional_string(
                data.get(
                    "started_at"
                )
            ),
            completed_at=self._optional_string(
                data.get(
                    "completed_at"
                )
            ),
            input_data=self._safe_dict(
                data.get(
                    "input_data",
                    {},
                )
            ),
            output_data=self._safe_dict(
                data.get(
                    "output_data",
                    {},
                )
            ),
            errors=self._unique_strings(
                self._safe_list(
                    data.get(
                        "errors",
                        [],
                    )
                )
            ),
            metadata=self._safe_dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )

    def _get_task(
        self,
        task_id: str,
    ) -> DevelopmentTask | None:

        return self._tasks.get(
            str(task_id).strip()
        )

    def _normalize_enum_value(
        self,
        value: Any,
        enum_class: type[Enum],
        default: str,
    ) -> str:

        normalized = str(
            value
        ).strip().upper()

        valid_values = {
            item.value
            for item in enum_class
        }

        if normalized in valid_values:
            return normalized

        return default

    def _ensure_storage(
        self,
    ) -> None:

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.storage_path.exists():
            self.storage_path.write_text(
                json.dumps(
                    {
                        "version": "1.0.0",
                        "saved_at": self._utc_now(),
                        "tasks": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def _save_if_enabled(
        self,
    ) -> None:

        if self.auto_save:
            self.save()

    def _safe_float(
        self,
        value: Any,
        default: float,
    ) -> float:

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_int(
        self,
        value: Any,
        default: int,
    ) -> int:

        try:
            return int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(
            value,
            list,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            tuple,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            set,
        ):
            return list(
                value
            )

        if value is None:
            return []

        return [
            value
        ]

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        return self._unique_strings(
            self._safe_list(
                value
            )
        )

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None

    def _unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            text = str(
                value
            ).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                text
            )

        return result

    def _utc_now(
        self,
    ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

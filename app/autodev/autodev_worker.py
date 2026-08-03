from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import threading
import time
import uuid

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.autodev.autonomous_task_queue import AutonomousTask
from app.autodev.developer_agent import DeveloperAgent
from app.autodev.developer_controller import DeveloperController
from app.autodev.developer_request import DeveloperRequest
from app.autodev.error_reporting import AutoDevErrorReporter
from app.autodev.autodev_worker_request_service import (
    AutoDevWorkerRequestService,
)


_AUTODEV_WORKER_REQUEST_SERVICE = AutoDevWorkerRequestService()


class WorkerState(StrEnum):
    IDLE = "idle"
    PREPARING = "preparing"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class AutoDevWorkerPolicy:
    project_root: str = default_project_root()
    auto_approve: bool = False
    auto_execute: bool = True
    auto_rollback: bool = True
    require_safe_metadata: bool = True
    max_changed_files: int = 5
    protected_paths: tuple[str, ...] = (
        ".git",
        ".venv",
        "data/backups",
        "AI_PLIKI",
    )
    allowed_modes: set[str] = field(
        default_factory=lambda: {
            "file",
            "function",
            "multi_file",
        }
    )

    def validate(self) -> None:
        if not self.project_root.strip():
            raise ValueError("project_root cannot be empty")

        if not self.allowed_modes:
            raise ValueError("allowed_modes cannot be empty")

        if self.max_changed_files < 1:
            raise ValueError(
                "max_changed_files must be at least 1"
            )


@dataclass(slots=True)
class AutoDevWorkerResult:
    success: bool
    status: str
    message: str
    task_id: str
    worker_id: str
    started_at: float
    finished_at: float
    duration_seconds: float
    approval_required: bool = False
    preview: str = ""
    changed_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    error_details: list[dict[str, Any]] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutoDevWorker:
    """
    Executes autonomous AutoDev tasks through the existing
    DeveloperController workflow.

    Expected task payload:
    {
        "goal": "...",
        "target": "...",
        "mode": "file" | "function" | "multi_file",
        "path": "...",
        "proposed_content": "...",
        "function_name": "...",
        "new_function_code": "...",
        "replacements": {...},
        "metadata": {...},
        "auto_approve": bool,
        "auto_execute": bool,
        "auto_rollback": bool
    }
    """

    def __init__(
        self,
        *,
        worker_id: str | None = None,
        policy: AutoDevWorkerPolicy | None = None,
        controller: DeveloperController | None = None,
        developer_agent: DeveloperAgent | None = None,
    ) -> None:
        self.policy = policy or AutoDevWorkerPolicy()
        self.policy.validate()

        self.worker_id = (
            worker_id.strip()
            if worker_id and worker_id.strip()
            else f"autodev-worker-{uuid.uuid4()}"
        )

        self.controller = controller or DeveloperController(
            project_root=self.policy.project_root
        )
        self.developer_agent = (
            developer_agent
            or DeveloperAgent(
                project_root=self.policy.project_root
            )
        )

        self._state = WorkerState.IDLE
        self._lock = threading.RLock()
        self._current_task_id: str | None = None
        self._last_result: AutoDevWorkerResult | None = None

    @property
    def state(self) -> WorkerState:
        with self._lock:
            return self._state

    @property
    def current_task_id(self) -> str | None:
        with self._lock:
            return self._current_task_id

    @property
    def last_result(self) -> AutoDevWorkerResult | None:
        with self._lock:
            return self._last_result

    def handle(self, task: AutonomousTask) -> dict[str, Any]:
        result = self.execute(task)
        return result.to_dict()

    def execute(
        self,
        task: AutonomousTask,
    ) -> AutoDevWorkerResult:
        started_at = time.time()

        with self._lock:
            if self._state not in {
                WorkerState.IDLE,
                WorkerState.COMPLETED,
                WorkerState.FAILED,
            }:
                raise RuntimeError(
                    f"Worker {self.worker_id} is busy"
                )

            self._state = WorkerState.PREPARING
            self._current_task_id = task.task_id
            self._last_result = None

        try:
            request = self._build_request(task)
            self._validate_task_policy(task, request)

            self.controller.reset()
            prepare_result = self.controller.prepare(request)

            if not prepare_result.success:
                return self._finish(
                    task=task,
                    started_at=started_at,
                    success=False,
                    status=prepare_result.status,
                    message=prepare_result.message,
                    errors=list(prepare_result.errors),
                    data=self._workflow_result_data(
                        prepare_result
                    ),
                )

            preview = prepare_result.preview or ""
            auto_approve = bool(
                task.payload.get(
                    "auto_approve",
                    self.policy.auto_approve,
                )
            )
            auto_execute = bool(
                task.payload.get(
                    "auto_execute",
                    self.policy.auto_execute,
                )
            )
            auto_rollback = bool(
                task.payload.get(
                    "auto_rollback",
                    self.policy.auto_rollback,
                )
            )

            if not auto_approve:
                with self._lock:
                    self._state = (
                        WorkerState.WAITING_FOR_APPROVAL
                    )

                return self._finish(
                    task=task,
                    started_at=started_at,
                    success=True,
                    status="waiting_for_approval",
                    message=prepare_result.message,
                    approval_required=True,
                    preview=preview,
                    data=self._workflow_result_data(
                        prepare_result
                    ),
                    final_state=(
                        WorkerState.WAITING_FOR_APPROVAL
                    ),
                )

            approval_result = self.controller.approve()

            if not approval_result.success:
                return self._finish(
                    task=task,
                    started_at=started_at,
                    success=False,
                    status=approval_result.status,
                    message=approval_result.message,
                    preview=preview,
                    errors=list(approval_result.errors),
                    data=self._workflow_result_data(
                        approval_result
                    ),
                )

            if not auto_execute:
                return self._finish(
                    task=task,
                    started_at=started_at,
                    success=True,
                    status="approved",
                    message=approval_result.message,
                    preview=preview,
                    approval_required=False,
                    data=self._workflow_result_data(
                        approval_result
                    ),
                )

            with self._lock:
                self._state = WorkerState.EXECUTING

            execution_result = self.controller.execute(
                auto_rollback=auto_rollback
            )

            changed_files = list(
                execution_result.data.get(
                    "changed_files",
                    [],
                )
            )

            if not changed_files:
                changed_files = list(
                    execution_result.data.get(
                        "transaction_files",
                        [],
                    )
                )

            return self._finish(
                task=task,
                started_at=started_at,
                success=execution_result.success,
                status=execution_result.status,
                message=execution_result.message,
                preview=preview,
                changed_files=changed_files,
                errors=list(execution_result.errors),
                data=self._workflow_result_data(
                    execution_result
                ),
            )

        except Exception as exc:
            report = AutoDevErrorReporter.capture(
                exc,
                stage="autodev_worker.execute",
                context={
                    "task_id": task.task_id,
                    "worker_id": self.worker_id,
                    "state": self._state.value,
                },
                project_root=self.policy.project_root,
            )

            return self._finish(
                task=task,
                started_at=started_at,
                success=False,
                status="worker_exception",
                message=(
                    "AutoDevWorker przerwał wykonanie zadania."
                ),
                errors=[
                    report.summary()
                ],
                error_details=[
                    report.as_dict()
                ],
                data={
                    "error_id": report.error_id,
                    "retryable": report.retryable,
                },
            )

    def approve_current(
        self,
        *,
        auto_execute: bool = True,
        auto_rollback: bool | None = None,
    ) -> AutoDevWorkerResult:
        with self._lock:
            if (
                self._state
                != WorkerState.WAITING_FOR_APPROVAL
            ):
                raise RuntimeError(
                    "Worker is not waiting for approval"
                )

            task_id = self._current_task_id or ""
            started_at = time.time()
            self._state = WorkerState.EXECUTING

        approval_result = self.controller.approve()

        if not approval_result.success:
            return self._finish_manual(
                task_id=task_id,
                started_at=started_at,
                success=False,
                status=approval_result.status,
                message=approval_result.message,
                errors=list(approval_result.errors),
                data=self._workflow_result_data(
                    approval_result
                ),
            )

        if not auto_execute:
            return self._finish_manual(
                task_id=task_id,
                started_at=started_at,
                success=True,
                status="approved",
                message=approval_result.message,
                data=self._workflow_result_data(
                    approval_result
                ),
            )

        execution_result = self.controller.execute(
            auto_rollback=(
                self.policy.auto_rollback
                if auto_rollback is None
                else auto_rollback
            )
        )

        return self._finish_manual(
            task_id=task_id,
            started_at=started_at,
            success=execution_result.success,
            status=execution_result.status,
            message=execution_result.message,
            changed_files=list(
                execution_result.data.get(
                    "changed_files",
                    [],
                )
            ),
            errors=list(execution_result.errors),
            data=self._workflow_result_data(
                execution_result
            ),
        )

    def reject_current(
        self,
        reason: str = "",
    ) -> AutoDevWorkerResult:
        with self._lock:
            if (
                self._state
                != WorkerState.WAITING_FOR_APPROVAL
            ):
                raise RuntimeError(
                    "Worker is not waiting for approval"
                )

            task_id = self._current_task_id or ""
            started_at = time.time()

        reject_result = self.controller.reject(reason)

        return self._finish_manual(
            task_id=task_id,
            started_at=started_at,
            success=reject_result.success,
            status=reject_result.status,
            message=reject_result.message,
            errors=list(reject_result.errors),
            data=self._workflow_result_data(
                reject_result
            ),
        )

    def rollback_last(self) -> AutoDevWorkerResult:
        started_at = time.time()
        result = self.controller.rollback_last()

        return self._finish_manual(
            task_id=self._current_task_id or "",
            started_at=started_at,
            success=result.success,
            status=result.status,
            message=result.message,
            errors=list(result.errors),
            data=self._workflow_result_data(result),
        )

    def _build_request(
        self,
        task: AutonomousTask,
    ) -> DeveloperRequest:
        return _AUTODEV_WORKER_REQUEST_SERVICE._build_request(
            self,
            task,
        )


    def _resolve_code_inputs(
        self,
        *,
        task: AutonomousTask,
        payload: dict[str, Any],
        goal: str,
        target: str,
        mode: str,
    ) -> dict[str, Any]:
        return _AUTODEV_WORKER_REQUEST_SERVICE._resolve_code_inputs(
            self,
            task=task,
            payload=payload,
            goal=goal,
            target=target,
            mode=mode,
        )


    @staticmethod
    @staticmethod
    def _find_code_proposal(
        value: Any,
    ) -> dict[str, Any]:
        return _AUTODEV_WORKER_REQUEST_SERVICE._find_code_proposal(
            value,
        )


    def _validate_task_policy(
        self,
        task: AutonomousTask,
        request: DeveloperRequest,
    ) -> None:
        if request.mode not in self.policy.allowed_modes:
            raise ValueError(
                f"Mode {request.mode!r} is not allowed"
            )

        if self.policy.require_safe_metadata:
            metadata = request.metadata or {}

            if metadata.get("unsafe") is True:
                raise PermissionError(
                    "Task metadata marks this task as unsafe"
                )

            if metadata.get("requires_human_review") is True:
                task.payload["auto_approve"] = False

        self._validate_paths(request)

    def _validate_paths(
        self,
        request: DeveloperRequest,
    ) -> None:
        project_root = Path(
            self.policy.project_root
        ).resolve()

        paths: list[str] = []

        if request.mode in {"file", "function"}:
            if request.path:
                paths.append(request.path)

        if request.mode == "multi_file":
            paths.extend(
                str(path)
                for path in request.replacements.keys()
            )

        if len(paths) > self.policy.max_changed_files:
            raise PermissionError(
                "AutoDev task changes too many files: "
                f"{len(paths)} > "
                f"{self.policy.max_changed_files}"
            )

        for raw_path in paths:
            candidate = Path(raw_path)

            if not candidate.is_absolute():
                candidate = project_root / candidate

            resolved = candidate.resolve()

            try:
                relative = resolved.relative_to(
                    project_root
                )
            except ValueError as exc:
                raise PermissionError(
                    "AutoDev task targets a path outside "
                    f"the project root: {resolved}"
                ) from exc

            normalized_relative = str(
                relative
            ).replace(
                "\\",
                "/",
            ).casefold()

            if any(
                normalized_relative == protected.casefold()
                or normalized_relative.startswith(
                    protected.casefold().rstrip("/")
                    + "/"
                )
                for protected in self.policy.protected_paths
            ):
                raise PermissionError(
                    "AutoDev task targets a protected path: "
                    f"{relative}"
                )

    def _workflow_result_data(
        self,
        result: Any,
    ) -> dict[str, Any]:
        data = dict(
            getattr(result, "data", {}) or {}
        )
        error_details = list(
            getattr(
                result,
                "error_details",
                [],
            )
            or []
        )

        if error_details:
            data.setdefault(
                "error_details",
                [
                    dict(item)
                    for item in error_details
                    if isinstance(
                        item,
                        dict,
                    )
                ],
            )

        transaction = getattr(
            result,
            "transaction",
            None,
        )

        if transaction is not None:
            data.setdefault(
                "transaction_status",
                getattr(
                    transaction,
                    "status",
                    "",
                ),
            )
            data.setdefault(
                "transaction_files",
                list(transaction.files()),
            )
            data.setdefault(
                "backup_bundle",
                getattr(
                    transaction,
                    "backup_bundle_path",
                    "",
                ),
            )

        return data

    def _finish(
        self,
        *,
        task: AutonomousTask,
        started_at: float,
        success: bool,
        status: str,
        message: str,
        approval_required: bool = False,
        preview: str = "",
        changed_files: list[str] | None = None,
        errors: list[str] | None = None,
        data: dict[str, Any] | None = None,
        error_details: list[dict[str, Any]] | None = None,
        final_state: WorkerState | None = None,
    ) -> AutoDevWorkerResult:
        finished_at = time.time()

        result = AutoDevWorkerResult(
            success=success,
            status=status,
            message=message,
            task_id=task.task_id,
            worker_id=self.worker_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=finished_at - started_at,
            approval_required=approval_required,
            preview=preview,
            changed_files=list(changed_files or []),
            errors=list(errors or []),
            data=dict(data or {}),
            error_details=[
                dict(item)
                for item in list(
                    error_details or []
                )
            ],
        )

        with self._lock:
            self._last_result = result

            if final_state is not None:
                self._state = final_state
            else:
                self._state = (
                    WorkerState.COMPLETED
                    if success
                    else WorkerState.FAILED
                )

            if self._state != (
                WorkerState.WAITING_FOR_APPROVAL
            ):
                self._current_task_id = None

        return result

    def _finish_manual(
        self,
        *,
        task_id: str,
        started_at: float,
        success: bool,
        status: str,
        message: str,
        changed_files: list[str] | None = None,
        errors: list[str] | None = None,
        data: dict[str, Any] | None = None,
        error_details: list[dict[str, Any]] | None = None,
    ) -> AutoDevWorkerResult:
        finished_at = time.time()

        result = AutoDevWorkerResult(
            success=success,
            status=status,
            message=message,
            task_id=task_id,
            worker_id=self.worker_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=finished_at - started_at,
            changed_files=list(changed_files or []),
            errors=list(errors or []),
            data=dict(data or {}),
            error_details=[
                dict(item)
                for item in list(
                    error_details or []
                )
            ],
        )

        with self._lock:
            self._last_result = result
            self._state = (
                WorkerState.COMPLETED
                if success
                else WorkerState.FAILED
            )
            self._current_task_id = None

        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "worker_id": self.worker_id,
                "state": self._state.value,
                "current_task_id": self._current_task_id,
                "policy": {
                    "project_root": self.policy.project_root,
                    "auto_approve": self.policy.auto_approve,
                    "auto_execute": self.policy.auto_execute,
                    "auto_rollback": self.policy.auto_rollback,
                    "require_safe_metadata": (
                        self.policy.require_safe_metadata
                    ),
                    "allowed_modes": sorted(
                        self.policy.allowed_modes
                    ),
                },
                "controller": self.controller.status(),
                "last_result": (
                    self._last_result.to_dict()
                    if self._last_result
                    else None
                ),
            }

    def reset(self) -> None:
        with self._lock:
            if self._state in {
                WorkerState.PREPARING,
                WorkerState.EXECUTING,
            }:
                raise RuntimeError(
                    "Cannot reset a busy worker"
                )

            self.controller.reset()
            self._state = WorkerState.IDLE
            self._current_task_id = None
            self._last_result = None

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class ExecutionCoordinatorStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class ExecutionCoordinatorAction(str, Enum):
    PREPARE = "PREPARE"
    APPROVE = "APPROVE"
    BACKUP = "BACKUP"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    ROLLBACK = "ROLLBACK"
    REPORT = "REPORT"


@dataclass
class ExecutionCoordinatorEvent:
    event_id: str
    action: str
    status: str
    message: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionCoordinatorResult:
    coordination_id: str
    cycle_id: str
    task_id: str | None
    status: str
    current_action: str | None
    prepared_payload: dict[str, Any]
    approval: dict[str, Any]
    backup: dict[str, Any]
    execution: dict[str, Any]
    validation: dict[str, Any]
    rollback: dict[str, Any]
    report: dict[str, Any]
    events: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionCoordinator:

    def __init__(
        self,
        developer_controller: Any | None = None,
        validator: Any | None = None,
        rollback_coordinator: Any | None = None,
    ) -> None:

        self.developer_controller = (
            developer_controller
        )

        self.validator = validator

        self.rollback_coordinator = (
            rollback_coordinator
        )

    def coordinate(
        self,
        cycle_id: str,
        plan: dict[str, Any],
        task: dict[str, Any] | None = None,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_cycle_id = str(
            cycle_id
        ).strip()

        if not normalized_cycle_id:
            raise ValueError(
                "ExecutionCoordinator wymaga cycle_id."
            )

        normalized_plan = self._safe_dict(
            plan
        )

        normalized_task = self._safe_dict(
            task
        )

        normalized_context = self._safe_dict(
            context
        )

        coordination_id = (
            f"execution_coordination_{uuid4().hex}"
        )

        events: list[
            ExecutionCoordinatorEvent
        ] = []

        errors: list[str] = []
        warnings: list[str] = []

        prepared_payload = self._prepare_payload(
            cycle_id=normalized_cycle_id,
            plan=normalized_plan,
            task=normalized_task,
            context=normalized_context,
        )

        self._add_event(
            events=events,
            action=ExecutionCoordinatorAction.PREPARE,
            status=ExecutionCoordinatorStatus.READY,
            message="Przygotowano payload wykonania.",
            metadata={
                "payload_available": bool(
                    prepared_payload
                ),
            },
        )

        approval_required = bool(
            normalized_plan.get(
                "requires_approval",
                True,
            )
        )

        approval = {
            "required": approval_required,
            "approved": approved,
        }

        if (
            approval_required
            and approved is not True
        ):
            self._add_event(
                events=events,
                action=ExecutionCoordinatorAction.APPROVE,
                status=(
                    ExecutionCoordinatorStatus
                    .WAITING_FOR_APPROVAL
                ),
                message=(
                    "Wymagana jest akceptacja "
                    "przed wykonaniem zmian."
                ),
            )

            return ExecutionCoordinatorResult(
                coordination_id=coordination_id,
                cycle_id=normalized_cycle_id,
                task_id=self._optional_string(
                    normalized_task.get(
                        "task_id"
                    )
                ),
                status=(
                    ExecutionCoordinatorStatus
                    .WAITING_FOR_APPROVAL
                    .value
                ),
                current_action=(
                    ExecutionCoordinatorAction
                    .APPROVE
                    .value
                ),
                prepared_payload=prepared_payload,
                approval=approval,
                backup={},
                execution={},
                validation={},
                rollback={},
                report={},
                events=[
                    event.to_dict()
                    for event in events
                ],
                errors=errors,
                warnings=warnings,
                metadata={
                    "coordinator_version": "1.0.0",
                },
            ).to_dict()

        self._add_event(
            events=events,
            action=ExecutionCoordinatorAction.APPROVE,
            status=ExecutionCoordinatorStatus.READY,
            message="Zmiana została zaakceptowana.",
        )

        backup = self._create_backup(
            prepared_payload
        )

        self._add_event(
            events=events,
            action=ExecutionCoordinatorAction.BACKUP,
            status=(
                ExecutionCoordinatorStatus.READY
                if self._detect_success(
                    backup
                )
                else ExecutionCoordinatorStatus.FAILED
            ),
            message=(
                "Backup przygotowany."
                if self._detect_success(
                    backup
                )
                else "Backup nie został przygotowany."
            ),
        )

        if not self._detect_success(
            backup
        ):
            errors.append(
                self._extract_error(
                    backup,
                    "Backup zakończył się błędem.",
                )
            )

            return self._build_result(
                coordination_id=coordination_id,
                cycle_id=normalized_cycle_id,
                task=normalized_task,
                status=ExecutionCoordinatorStatus.FAILED,
                current_action=ExecutionCoordinatorAction.BACKUP,
                prepared_payload=prepared_payload,
                approval=approval,
                backup=backup,
                execution={},
                validation={},
                rollback={},
                report={},
                events=events,
                errors=errors,
                warnings=warnings,
            )

        execution = self._execute(
            prepared_payload
        )

        self._add_event(
            events=events,
            action=ExecutionCoordinatorAction.EXECUTE,
            status=(
                ExecutionCoordinatorStatus.RUNNING
                if self._detect_success(
                    execution
                )
                else ExecutionCoordinatorStatus.FAILED
            ),
            message=(
                "Wykonanie zmian zakończone."
                if self._detect_success(
                    execution
                )
                else "Wykonanie zmian nie powiodło się."
            ),
        )

        if not self._detect_success(
            execution
        ):
            errors.append(
                self._extract_error(
                    execution,
                    "DeveloperController zakończył się błędem.",
                )
            )

            rollback = self._rollback(
                backup=backup,
                execution=execution,
                validation={},
                context=normalized_context,
            )

            self._add_event(
                events=events,
                action=ExecutionCoordinatorAction.ROLLBACK,
                status=(
                    ExecutionCoordinatorStatus.ROLLED_BACK
                    if self._detect_success(
                        rollback
                    )
                    else ExecutionCoordinatorStatus.FAILED
                ),
                message=(
                    "Rollback zakończył się sukcesem."
                    if self._detect_success(
                        rollback
                    )
                    else "Rollback nie powiódł się."
                ),
            )

            return self._build_result(
                coordination_id=coordination_id,
                cycle_id=normalized_cycle_id,
                task=normalized_task,
                status=(
                    ExecutionCoordinatorStatus.ROLLED_BACK
                    if self._detect_success(
                        rollback
                    )
                    else ExecutionCoordinatorStatus.FAILED
                ),
                current_action=ExecutionCoordinatorAction.ROLLBACK,
                prepared_payload=prepared_payload,
                approval=approval,
                backup=backup,
                execution=execution,
                validation={},
                rollback=rollback,
                report={},
                events=events,
                errors=errors,
                warnings=warnings,
            )

        validation = self._validate(
            prepared_payload=prepared_payload,
            execution=execution,
        )

        self._add_event(
            events=events,
            action=ExecutionCoordinatorAction.VALIDATE,
            status=(
                ExecutionCoordinatorStatus.COMPLETED
                if self._detect_success(
                    validation
                )
                else ExecutionCoordinatorStatus.FAILED
            ),
            message=(
                "Walidacja zakończyła się sukcesem."
                if self._detect_success(
                    validation
                )
                else "Walidacja zakończyła się błędem."
            ),
        )

        rollback: dict[str, Any] = {}

        if not self._detect_success(
            validation
        ):
            errors.append(
                self._extract_error(
                    validation,
                    "Walidacja zakończyła się błędem.",
                )
            )

            rollback = self._rollback(
                backup=backup,
                execution=execution,
                validation=validation,
                context=normalized_context,
            )

            self._add_event(
                events=events,
                action=ExecutionCoordinatorAction.ROLLBACK,
                status=(
                    ExecutionCoordinatorStatus.ROLLED_BACK
                    if self._detect_success(
                        rollback
                    )
                    else ExecutionCoordinatorStatus.FAILED
                ),
                message=(
                    "Rollback zakończył się sukcesem."
                    if self._detect_success(
                        rollback
                    )
                    else "Rollback nie powiódł się."
                ),
            )

            return self._build_result(
                coordination_id=coordination_id,
                cycle_id=normalized_cycle_id,
                task=normalized_task,
                status=(
                    ExecutionCoordinatorStatus.ROLLED_BACK
                    if self._detect_success(
                        rollback
                    )
                    else ExecutionCoordinatorStatus.FAILED
                ),
                current_action=ExecutionCoordinatorAction.ROLLBACK,
                prepared_payload=prepared_payload,
                approval=approval,
                backup=backup,
                execution=execution,
                validation=validation,
                rollback=rollback,
                report={},
                events=events,
                errors=errors,
                warnings=warnings,
            )

        report = self._build_report(
            cycle_id=normalized_cycle_id,
            plan=normalized_plan,
            task=normalized_task,
            backup=backup,
            execution=execution,
            validation=validation,
            rollback=rollback,
        )

        self._add_event(
            events=events,
            action=ExecutionCoordinatorAction.REPORT,
            status=ExecutionCoordinatorStatus.COMPLETED,
            message="Przygotowano raport wykonania.",
        )

        return self._build_result(
            coordination_id=coordination_id,
            cycle_id=normalized_cycle_id,
            task=normalized_task,
            status=ExecutionCoordinatorStatus.COMPLETED,
            current_action=ExecutionCoordinatorAction.REPORT,
            prepared_payload=prepared_payload,
            approval=approval,
            backup=backup,
            execution=execution,
            validation=validation,
            rollback=rollback,
            report=report,
            events=events,
            errors=errors,
            warnings=warnings,
        )

    def execute(
        self,
        cycle_id: str,
        plan: dict[str, Any],
        task: dict[str, Any] | None = None,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.coordinate(
            cycle_id=cycle_id,
            plan=plan,
            task=task,
            approved=approved,
            context=context,
        )

    def _prepare_payload(
        self,
        cycle_id: str,
        plan: dict[str, Any],
        task: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "cycle_id": cycle_id,
            "task_id": task.get(
                "task_id"
            ),
            "plan_id": plan.get(
                "plan_id"
            ),
            "improvement_id": plan.get(
                "improvement_id"
            ),
            "objective": plan.get(
                "objective",
                plan.get(
                    "title",
                    "",
                ),
            ),
            "strategy": plan.get(
                "strategy"
            ),
            "execution_order": plan.get(
                "execution_order",
                [],
            ),
            "steps": plan.get(
                "steps",
                [],
            ),
            "affected_files": self._safe_dict(
                plan.get(
                    "metadata",
                    {},
                )
            ).get(
                "affected_files",
                [],
            ),
            "context": context,
        }

    def _create_backup(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        controller = self.developer_controller

        if controller is None:
            return {
                "success": True,
                "status": "SKIPPED",
                "message": (
                    "Brak DeveloperController; "
                    "backup oznaczony jako pominięty."
                ),
            }

        if hasattr(
            controller,
            "create_backup",
        ):
            result = controller.create_backup(
                payload
            )

        elif hasattr(
            controller,
            "backup",
        ):
            result = controller.backup(
                payload
            )

        else:
            return {
                "success": True,
                "status": "NOT_SUPPORTED",
                "message": (
                    "DeveloperController nie posiada "
                    "osobnej metody backup."
                ),
            }

        return self._normalize_result(
            result
        )

    def _execute(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        controller = self.developer_controller

        if controller is None:
            return {
                "success": False,
                "status": "NO_CONTROLLER",
                "error": (
                    "DeveloperController nie został podłączony."
                ),
            }

        if hasattr(
            controller,
            "execute_strategy",
        ):
            result = controller.execute_strategy(
                payload
            )

        elif hasattr(
            controller,
            "execute",
        ):
            result = controller.execute(
                payload
            )

        elif hasattr(
            controller,
            "run",
        ):
            result = controller.run(
                payload
            )

        elif hasattr(
            controller,
            "process",
        ):
            result = controller.process(
                payload
            )

        elif callable(
            controller
        ):
            result = controller(
                payload
            )

        else:
            return {
                "success": False,
                "status": "UNSUPPORTED_CONTROLLER",
                "error": (
                    "DeveloperController nie posiada "
                    "obsługiwanej metody wykonania."
                ),
            }

        return self._normalize_result(
            result
        )

    def _validate(
        self,
        prepared_payload: dict[str, Any],
        execution: dict[str, Any],
    ) -> dict[str, Any]:

        validator = self.validator

        if validator is None:
            validation = execution.get(
                "validation"
            )

            if isinstance(
                validation,
                dict,
            ):
                return dict(
                    validation
                )

            return {
                "success": True,
                "status": "SKIPPED",
                "message": (
                    "Brak zewnętrznego validatora."
                ),
            }

        if hasattr(
            validator,
            "validate",
        ):
            result = validator.validate(
                prepared_payload,
                execution,
            )

        elif hasattr(
            validator,
            "run",
        ):
            result = validator.run(
                prepared_payload,
                execution,
            )

        elif callable(
            validator
        ):
            result = validator(
                prepared_payload,
                execution,
            )

        else:
            return {
                "success": False,
                "status": "UNSUPPORTED_VALIDATOR",
                "error": (
                    "Validator nie posiada obsługiwanej metody."
                ),
            }

        return self._normalize_result(
            result
        )

    def _rollback(
        self,
        backup: dict[str, Any],
        execution: dict[str, Any],
        validation: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        coordinator = self.rollback_coordinator

        payload = {
            "backup": backup,
            "execution": execution,
            "validation": validation,
            "context": context,
        }

        if coordinator is not None:
            if hasattr(
                coordinator,
                "rollback",
            ):
                result = coordinator.rollback(
                    payload
                )

            elif hasattr(
                coordinator,
                "execute",
            ):
                result = coordinator.execute(
                    payload
                )

            elif callable(
                coordinator
            ):
                result = coordinator(
                    payload
                )

            else:
                return {
                    "success": False,
                    "status": "UNSUPPORTED_ROLLBACK",
                    "error": (
                        "RollbackCoordinator nie posiada "
                        "obsługiwanej metody."
                    ),
                }

            return self._normalize_result(
                result
            )

        controller = self.developer_controller

        if controller is not None:
            if hasattr(
                controller,
                "rollback",
            ):
                result = controller.rollback(
                    payload
                )

                return self._normalize_result(
                    result
                )

        embedded = execution.get(
            "rollback"
        )

        if isinstance(
            embedded,
            dict,
        ):
            return dict(
                embedded
            )

        return {
            "success": False,
            "status": "NO_ROLLBACK_HANDLER",
            "error": (
                "Brak obsługi rollback."
            ),
        }

    def _build_report(
        self,
        cycle_id: str,
        plan: dict[str, Any],
        task: dict[str, Any],
        backup: dict[str, Any],
        execution: dict[str, Any],
        validation: dict[str, Any],
        rollback: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "success": True,
            "status": "COMPLETED",
            "cycle_id": cycle_id,
            "task_id": task.get(
                "task_id"
            ),
            "plan_id": plan.get(
                "plan_id"
            ),
            "backup_status": backup.get(
                "status"
            ),
            "execution_status": execution.get(
                "status"
            ),
            "validation_status": validation.get(
                "status"
            ),
            "rollback_status": rollback.get(
                "status"
            )
            if rollback
            else None,
        }

    def _build_result(
        self,
        coordination_id: str,
        cycle_id: str,
        task: dict[str, Any],
        status: ExecutionCoordinatorStatus,
        current_action: ExecutionCoordinatorAction,
        prepared_payload: dict[str, Any],
        approval: dict[str, Any],
        backup: dict[str, Any],
        execution: dict[str, Any],
        validation: dict[str, Any],
        rollback: dict[str, Any],
        report: dict[str, Any],
        events: list[ExecutionCoordinatorEvent],
        errors: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:

        return ExecutionCoordinatorResult(
            coordination_id=coordination_id,
            cycle_id=cycle_id,
            task_id=self._optional_string(
                task.get(
                    "task_id"
                )
            ),
            status=status.value,
            current_action=current_action.value,
            prepared_payload=prepared_payload,
            approval=approval,
            backup=backup,
            execution=execution,
            validation=validation,
            rollback=rollback,
            report=report,
            events=[
                event.to_dict()
                for event in events
            ],
            errors=self._unique_strings(
                errors
            ),
            warnings=self._unique_strings(
                warnings
            ),
            metadata={
                "coordinator_version": "1.0.0",
            },
        ).to_dict()

    def _add_event(
        self,
        events: list[ExecutionCoordinatorEvent],
        action: ExecutionCoordinatorAction,
        status: ExecutionCoordinatorStatus,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        from datetime import datetime, timezone

        events.append(
            ExecutionCoordinatorEvent(
                event_id=(
                    f"execution_event_{uuid4().hex}"
                ),
                action=action.value,
                status=status.value,
                message=str(
                    message
                ),
                timestamp=datetime.now(
                    timezone.utc
                ).isoformat(),
                metadata=self._safe_dict(
                    metadata
                ),
            )
        )

    def _normalize_result(
        self,
        result: Any,
    ) -> dict[str, Any]:

        if isinstance(
            result,
            dict,
        ):
            return dict(
                result
            )

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _detect_success(
        self,
        result: dict[str, Any],
    ) -> bool:

        value = result.get(
            "success"
        )

        if isinstance(
            value,
            bool,
        ):
            return value

        status = str(
            result.get(
                "status",
                "",
            )
        ).upper()

        return status in {
            "SUCCESS",
            "COMPLETED",
            "DONE",
            "VALIDATED",
            "PASSED",
            "SKIPPED",
            "NOT_SUPPORTED",
        }

    def _extract_error(
        self,
        result: dict[str, Any],
        fallback: str,
    ) -> str:

        for key in (
            "error",
            "message",
            "details",
        ):
            value = result.get(
                key
            )

            if value:
                return str(
                    value
                )

        return fallback

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

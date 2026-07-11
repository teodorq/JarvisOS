from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class RollbackStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RollbackReason(str, Enum):
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SECURITY_RISK = "SECURITY_RISK"
    MANUAL_REQUEST = "MANUAL_REQUEST"
    UNKNOWN = "UNKNOWN"


@dataclass
class RollbackEvent:
    event_id: str
    status: str
    message: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackResult:
    rollback_id: str
    cycle_id: str | None
    status: str
    success: bool
    reason: str
    backup: dict[str, Any]
    execution: dict[str, Any]
    validation: dict[str, Any]
    restored_files: list[str]
    failed_files: list[str]
    events: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RollbackCoordinator:

    def __init__(
        self,
        rollback_manager: Any | None = None,
        developer_controller: Any | None = None,
    ) -> None:

        self.rollback_manager = rollback_manager
        self.developer_controller = developer_controller

    def rollback(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        normalized = self._safe_dict(
            payload
        )

        cycle_id = self._optional_string(
            normalized.get(
                "cycle_id"
            )
        )

        backup = self._safe_dict(
            normalized.get(
                "backup",
                {},
            )
        )

        execution = self._safe_dict(
            normalized.get(
                "execution",
                {},
            )
        )

        validation = self._safe_dict(
            normalized.get(
                "validation",
                {},
            )
        )

        context = self._safe_dict(
            normalized.get(
                "context",
                {},
            )
        )

        reason = self._resolve_reason(
            execution=execution,
            validation=validation,
            context=context,
        )

        rollback_id = (
            f"rollback_coordination_{uuid4().hex}"
        )

        events: list[RollbackEvent] = []
        errors: list[str] = []
        warnings: list[str] = []

        self._add_event(
            events=events,
            status=RollbackStatus.CREATED,
            message="Utworzono operację rollback.",
        )

        if not backup:
            warning = (
                "Brak danych backupu; rollback "
                "nie może zostać wykonany bezpiecznie."
            )

            warnings.append(warning)

            self._add_event(
                events=events,
                status=RollbackStatus.SKIPPED,
                message=warning,
            )

            return RollbackResult(
                rollback_id=rollback_id,
                cycle_id=cycle_id,
                status=RollbackStatus.SKIPPED.value,
                success=False,
                reason=reason,
                backup=backup,
                execution=execution,
                validation=validation,
                restored_files=[],
                failed_files=[],
                events=[
                    event.to_dict()
                    for event in events
                ],
                errors=[],
                warnings=warnings,
                metadata={
                    "rollback_version": "1.0.0",
                },
            ).to_dict()

        self._add_event(
            events=events,
            status=RollbackStatus.READY,
            message="Rollback jest gotowy do wykonania.",
        )

        raw_result = self._execute_rollback(
            backup=backup,
            execution=execution,
            validation=validation,
            context=context,
        )

        normalized_result = self._normalize_result(
            raw_result
        )

        success = self._detect_success(
            normalized_result
        )

        restored_files = self._safe_string_list(
            normalized_result.get(
                "restored_files",
                normalized_result.get(
                    "files_restored",
                    [],
                ),
            )
        )

        failed_files = self._safe_string_list(
            normalized_result.get(
                "failed_files",
                [],
            )
        )

        errors.extend(
            self._collect_errors(
                normalized_result
            )
        )

        warnings.extend(
            self._safe_string_list(
                normalized_result.get(
                    "warnings",
                    [],
                )
            )
        )

        if success and not failed_files:
            status = RollbackStatus.COMPLETED.value
            message = "Rollback zakończył się sukcesem."

        elif success and failed_files:
            status = RollbackStatus.PARTIAL.value
            message = (
                "Rollback zakończył się częściowo."
            )

        else:
            status = RollbackStatus.FAILED.value
            message = "Rollback zakończył się błędem."

        self._add_event(
            events=events,
            status=RollbackStatus(
                status
            ),
            message=message,
            metadata={
                "restored_files_count": len(
                    restored_files
                ),
                "failed_files_count": len(
                    failed_files
                ),
            },
        )

        return RollbackResult(
            rollback_id=rollback_id,
            cycle_id=cycle_id,
            status=status,
            success=success,
            reason=reason,
            backup=backup,
            execution=execution,
            validation=validation,
            restored_files=restored_files,
            failed_files=failed_files,
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
                "rollback_version": "1.0.0",
                "handler": normalized_result.get(
                    "handler"
                ),
            },
        ).to_dict()

    def execute(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        return self.rollback(
            payload
        )

    def _execute_rollback(
        self,
        backup: dict[str, Any],
        execution: dict[str, Any],
        validation: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:

        payload = {
            "backup": backup,
            "execution": execution,
            "validation": validation,
            "context": context,
        }

        manager = self.rollback_manager

        if manager is not None:
            if hasattr(
                manager,
                "rollback",
            ):
                result = manager.rollback(
                    payload
                )

            elif hasattr(
                manager,
                "restore",
            ):
                result = manager.restore(
                    payload
                )

            elif hasattr(
                manager,
                "execute",
            ):
                result = manager.execute(
                    payload
                )

            elif callable(
                manager
            ):
                result = manager(
                    payload
                )

            else:
                return {
                    "success": False,
                    "status": "UNSUPPORTED_MANAGER",
                    "error": (
                        "RollbackManager nie posiada "
                        "obsługiwanej metody."
                    ),
                }

            normalized = self._normalize_result(
                result
            )

            normalized["handler"] = (
                "rollback_manager"
            )

            return normalized

        controller = self.developer_controller

        if controller is not None:
            if hasattr(
                controller,
                "rollback",
            ):
                result = controller.rollback(
                    payload
                )

                normalized = self._normalize_result(
                    result
                )

                normalized["handler"] = (
                    "developer_controller"
                )

                return normalized

            if hasattr(
                controller,
                "restore_backup",
            ):
                result = controller.restore_backup(
                    payload
                )

                normalized = self._normalize_result(
                    result
                )

                normalized["handler"] = (
                    "developer_controller"
                )

                return normalized

        embedded = execution.get(
            "rollback"
        )

        if isinstance(
            embedded,
            dict,
        ):
            normalized = dict(
                embedded
            )

            normalized["handler"] = (
                "embedded_execution_result"
            )

            return normalized

        return {
            "success": False,
            "status": "NO_ROLLBACK_HANDLER",
            "error": (
                "Brak RollbackManager i obsługi "
                "rollback w DeveloperController."
            ),
        }

    def _resolve_reason(
        self,
        execution: dict[str, Any],
        validation: dict[str, Any],
        context: dict[str, Any],
    ) -> str:

        explicit_reason = context.get(
            "rollback_reason"
        )

        if explicit_reason is not None:
            normalized = str(
                explicit_reason
            ).strip().upper()

            valid = {
                item.value
                for item in RollbackReason
            }

            if normalized in valid:
                return normalized

        if not self._detect_success(
            validation
        ) and validation:
            return RollbackReason.VALIDATION_FAILED.value

        if not self._detect_success(
            execution
        ) and execution:
            return RollbackReason.EXECUTION_FAILED.value

        if context.get(
            "security_risk"
        ) is True:
            return RollbackReason.SECURITY_RISK.value

        if context.get(
            "manual_request"
        ) is True:
            return RollbackReason.MANUAL_REQUEST.value

        return RollbackReason.UNKNOWN.value

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

        if isinstance(
            result,
            bool,
        ):
            return {
                "success": result,
                "status": (
                    "COMPLETED"
                    if result
                    else "FAILED"
                ),
            }

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _detect_success(
        self,
        result: dict[str, Any],
    ) -> bool:

        if not result:
            return False

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
            "RESTORED",
            "ROLLED_BACK",
            "PARTIAL",
        }

    def _collect_errors(
        self,
        result: dict[str, Any],
    ) -> list[str]:

        errors = self._safe_string_list(
            result.get(
                "errors",
                [],
            )
        )

        error = result.get(
            "error"
        )

        if error:
            errors.append(
                str(error)
            )

        return self._unique_strings(
            errors
        )

    def _add_event(
        self,
        events: list[RollbackEvent],
        status: RollbackStatus,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        from datetime import datetime, timezone

        events.append(
            RollbackEvent(
                event_id=f"rollback_event_{uuid4().hex}",
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

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionRecoveryPolicy:
    max_attempts: int = 3
    auto_approve: bool = True
    auto_rollback: bool = True
    retryable_categories: tuple[str, ...] = (
        "SYNTAX",
        "TEST_FAILURE",
        "IMPORT",
        "GENERATION",
    )
    stop_on_preview: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "max_attempts musi być większe od zera."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionAttempt:
    number: int
    status: str
    success: bool
    retryable: bool
    failure_category: str
    rollback_attempted: bool
    rollback_success: bool
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "status": self.status,
            "success": self.success,
            "retryable": self.retryable,
            "failure_category": self.failure_category,
            "rollback_attempted": self.rollback_attempted,
            "rollback_success": self.rollback_success,
            "errors": list(self.errors),
        }


class ExecutionRecoveryOrchestrator:
    """Runs ImplementationExecutor with bounded retry and rollback rules."""

    def __init__(
        self,
        *,
        implementation_executor: object,
        policy: ExecutionRecoveryPolicy | None = None,
    ) -> None:
        self.implementation_executor = (
            implementation_executor
        )
        self.policy = (
            policy
            or ExecutionRecoveryPolicy()
        )

    def execute_with_recovery(
        self,
        scheduled_task: dict[str, Any] | object,
    ) -> dict[str, Any]:
        normalized = self._normalize_task(
            scheduled_task
        )

        if not normalized:
            return {
                "success": False,
                "status": "INVALID_SCHEDULED_TASK",
                "attempt_count": 0,
                "attempts": [],
                "final_result": {},
                "errors": [
                    (
                        "Zadanie musi być słownikiem "
                        "lub obiektem z to_dict()."
                    )
                ],
            }

        current_task = normalized
        history: list[ExecutionAttempt] = []
        final_result: dict[str, Any] = {}

        for attempt_number in range(
            1,
            self.policy.max_attempts + 1,
        ):
            raw_result = (
                self.implementation_executor.execute(
                    current_task,
                    auto_approve=(
                        self.policy.auto_approve
                    ),
                    auto_rollback=(
                        self.policy.auto_rollback
                    ),
                )
            )
            final_result = self._result_dict(
                raw_result
            )

            attempt = self._attempt_from_result(
                number=attempt_number,
                result=final_result,
            )
            history.append(attempt)

            terminal_status = self._terminal_status(
                attempt=attempt,
                result=final_result,
                attempt_number=attempt_number,
            )

            if terminal_status is not None:
                return self._final_response(
                    status=terminal_status,
                    history=history,
                    final_result=final_result,
                )

            current_task = self._retry_task(
                original=normalized,
                previous=current_task,
                attempt=attempt,
                result=final_result,
            )

        return self._final_response(
            status="RETRY_EXHAUSTED",
            history=history,
            final_result=final_result,
        )

    def _terminal_status(
        self,
        *,
        attempt: ExecutionAttempt,
        result: dict[str, Any],
        attempt_number: int,
    ) -> str | None:
        if attempt.success:
            return "COMPLETED"

        if (
            attempt.status == "PREVIEW_READY"
            and self.policy.stop_on_preview
        ):
            return "PREVIEW_READY"

        if (
            attempt.rollback_attempted
            and not attempt.rollback_success
        ):
            return "ROLLBACK_FAILED"

        if not attempt.retryable:
            return "NON_RETRYABLE_FAILURE"

        if (
            attempt.failure_category
            not in {
                item.upper()
                for item
                in self.policy.retryable_categories
            }
        ):
            return "NON_RETRYABLE_FAILURE"

        if attempt_number >= self.policy.max_attempts:
            return "RETRY_EXHAUSTED"

        return None

    def _attempt_from_result(
        self,
        *,
        number: int,
        result: dict[str, Any],
    ) -> ExecutionAttempt:
        workflow = self._workflow(result)
        workflow_data = self._mapping(
            workflow.get("data")
        )
        analysis = self._mapping(
            workflow_data.get(
                "failure_analysis",
                result.get(
                    "failure_analysis",
                    {},
                ),
            )
        )

        status = str(
            result.get(
                "status",
                workflow.get(
                    "status",
                    "UNKNOWN",
                ),
            )
        ).strip().upper()

        errors = self._errors(
            result=result,
            workflow=workflow,
            analysis=analysis,
        )

        rollback_attempted = bool(
            workflow_data.get(
                "rollback_attempted",
                False,
            )
        )
        rollback_success = bool(
            workflow_data.get(
                "rollback_success",
                False,
            )
        )

        category = str(
            analysis.get(
                "category",
                "UNKNOWN",
            )
        ).strip().upper()
        retryable = bool(
            analysis.get(
                "retryable",
                False,
            )
        )

        if category == "UNKNOWN":
            if status == "PROPOSAL_FAILED":
                category = "GENERATION"
                retryable = True
            elif status in {
                "TARGET_REQUIRED",
                "TARGET_INVALID",
                "TARGET_PREPARATION_FAILED",
                "NON_CODE_TASK",
            }:
                category = "CONFIGURATION"
                retryable = False

        return ExecutionAttempt(
            number=number,
            status=status,
            success=bool(
                result.get(
                    "success",
                    workflow.get(
                        "success",
                        False,
                    ),
                )
            ),
            retryable=retryable,
            failure_category=category,
            rollback_attempted=rollback_attempted,
            rollback_success=rollback_success,
            errors=tuple(errors),
        )

    def _retry_task(
        self,
        *,
        original: dict[str, Any],
        previous: dict[str, Any],
        attempt: ExecutionAttempt,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        task = dict(original)
        payload = self._mapping(
            task.get("payload")
        )
        metadata = self._mapping(
            payload.get("metadata")
        )

        for container in (
            task,
            payload,
            metadata,
        ):
            container.pop(
                "proposed_content",
                None,
            )
            container.pop(
                "new_content",
                None,
            )

        original_description = str(
            payload.get(
                "description",
                task.get(
                    "description",
                    task.get(
                        "title",
                        "Wykonaj zadanie implementacyjne.",
                    ),
                ),
            )
        ).strip()

        feedback = self._retry_feedback(
            attempt=attempt,
            result=result,
        )

        payload["description"] = (
            f"{original_description}\n\n"
            "POPRZEDNIA PRÓBA NIE POWIODŁA SIĘ.\n"
            f"{feedback}\n"
            "Wygeneruj nową, pełną i minimalną "
            "wersję pliku, która usuwa wskazany błąd."
        )
        metadata["recovery"] = {
            "attempt": attempt.number,
            "failure_category": (
                attempt.failure_category
            ),
            "errors": list(
                attempt.errors
            ),
            "previous_status": attempt.status,
        }
        payload["metadata"] = metadata
        payload["retry_context"] = {
            "attempt": attempt.number,
            "failure_category": (
                attempt.failure_category
            ),
            "errors": list(
                attempt.errors
            ),
        }
        task["payload"] = payload

        return task

    @staticmethod
    def _retry_feedback(
        *,
        attempt: ExecutionAttempt,
        result: dict[str, Any],
    ) -> str:
        details = [
            (
                "Kategoria błędu: "
                f"{attempt.failure_category}"
            ),
            (
                "Status poprzedniej próby: "
                f"{attempt.status}"
            ),
        ]

        if attempt.errors:
            details.append(
                "Błędy:\n- "
                + "\n- ".join(
                    attempt.errors[-8:]
                )
            )

        return "\n".join(details)

    def _final_response(
        self,
        *,
        status: str,
        history: list[ExecutionAttempt],
        final_result: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "success": status == "COMPLETED",
            "status": status,
            "attempt_count": len(history),
            "max_attempts": (
                self.policy.max_attempts
            ),
            "attempts": [
                attempt.to_dict()
                for attempt in history
            ],
            "final_result": final_result,
            "rollback_used": any(
                attempt.rollback_success
                for attempt in history
            ),
            "retry_used": len(history) > 1,
            "errors": (
                list(
                    history[-1].errors
                )
                if history
                else []
            ),
        }

    @staticmethod
    def _workflow(
        result: dict[str, Any],
    ) -> dict[str, Any]:
        return ExecutionRecoveryOrchestrator._mapping(
            result.get("workflow")
        )

    @staticmethod
    def _errors(
        *,
        result: dict[str, Any],
        workflow: dict[str, Any],
        analysis: dict[str, Any],
    ) -> list[str]:
        values: list[str] = []

        for candidate in (
            result.get("errors"),
            workflow.get("errors"),
            analysis.get("errors"),
        ):
            if isinstance(
                candidate,
                (list, tuple),
            ):
                values.extend(
                    str(item)
                    for item in candidate
                    if str(item).strip()
                )
            elif candidate:
                values.append(
                    str(candidate)
                )

        message = str(
            analysis.get(
                "message",
                workflow.get(
                    "message",
                    "",
                ),
            )
        ).strip()

        if message:
            values.append(message)

        unique: list[str] = []

        for value in values:
            if value not in unique:
                unique.append(value)

        return unique[-20:]

    @staticmethod
    def _result_dict(
        result: object,
    ) -> dict[str, Any]:
        if isinstance(result, dict):
            return dict(result)

        as_dict = getattr(
            result,
            "as_dict",
            None,
        )

        if callable(as_dict):
            value = as_dict()

            if isinstance(value, dict):
                return dict(value)

        return {
            "success": bool(
                getattr(
                    result,
                    "success",
                    False,
                )
            ),
            "status": str(
                getattr(
                    result,
                    "status",
                    "UNKNOWN",
                )
            ),
            "errors": list(
                getattr(
                    result,
                    "errors",
                    [],
                )
                or []
            ),
        }

    @staticmethod
    def _normalize_task(
        scheduled_task: dict[str, Any] | object,
    ) -> dict[str, Any]:
        if isinstance(
            scheduled_task,
            dict,
        ):
            return dict(
                scheduled_task
            )

        to_dict = getattr(
            scheduled_task,
            "to_dict",
            None,
        )

        if callable(to_dict):
            value = to_dict()

            if isinstance(value, dict):
                return dict(value)

        return {}

    @staticmethod
    def _mapping(
        value: object,
    ) -> dict[str, Any]:
        return (
            dict(value)
            if isinstance(value, dict)
            else {}
        )

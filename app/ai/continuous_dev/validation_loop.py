from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class ValidationLoopStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    RETRY_REQUIRED = "RETRY_REQUIRED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    CANCELLED = "CANCELLED"


class ValidationCheckType(str, Enum):
    SYNTAX = "SYNTAX"
    IMPORTS = "IMPORTS"
    UNIT_TESTS = "UNIT_TESTS"
    INTEGRATION_TESTS = "INTEGRATION_TESTS"
    FUNCTIONAL = "FUNCTIONAL"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    CUSTOM = "CUSTOM"


@dataclass
class ValidationCheckResult:
    check_id: str
    check_type: str
    name: str
    success: bool
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationLoopResult:
    validation_id: str
    cycle_id: str
    status: str
    success: bool
    attempt: int
    max_attempts: int
    checks: list[dict[str, Any]]
    failed_checks: list[str]
    warnings: list[str]
    errors: list[str]
    retry_recommended: bool
    rollback_required: bool
    confidence: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ValidationLoop:

    def __init__(
        self,
        validators: dict[str, Any] | None = None,
        max_attempts: int = 3,
        require_all_checks: bool = True,
    ) -> None:

        self.validators = (
            dict(validators)
            if isinstance(validators, dict)
            else {}
        )

        self.max_attempts = max(
            1,
            int(max_attempts),
        )

        self.require_all_checks = bool(
            require_all_checks
        )

    def validate(
        self,
        cycle_id: str,
        execution_result: dict[str, Any],
        plan: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        attempt: int = 1,
    ) -> dict[str, Any]:

        normalized_cycle_id = str(
            cycle_id
        ).strip()

        if not normalized_cycle_id:
            raise ValueError(
                "ValidationLoop wymaga cycle_id."
            )

        normalized_execution = self._safe_dict(
            execution_result
        )

        normalized_plan = self._safe_dict(
            plan
        )

        normalized_context = self._safe_dict(
            context
        )

        normalized_attempt = max(
            1,
            int(attempt),
        )

        checks: list[
            ValidationCheckResult
        ] = []

        checks.append(
            self._run_builtin_check(
                check_type=ValidationCheckType.SYNTAX,
                name="Walidacja składni",
                execution=normalized_execution,
                plan=normalized_plan,
                context=normalized_context,
            )
        )

        checks.append(
            self._run_builtin_check(
                check_type=ValidationCheckType.IMPORTS,
                name="Walidacja importów",
                execution=normalized_execution,
                plan=normalized_plan,
                context=normalized_context,
            )
        )

        checks.append(
            self._run_builtin_check(
                check_type=ValidationCheckType.UNIT_TESTS,
                name="Testy jednostkowe",
                execution=normalized_execution,
                plan=normalized_plan,
                context=normalized_context,
            )
        )

        if normalized_context.get(
            "run_integration_tests",
            True,
        ):
            checks.append(
                self._run_builtin_check(
                    check_type=ValidationCheckType.INTEGRATION_TESTS,
                    name="Testy integracyjne",
                    execution=normalized_execution,
                    plan=normalized_plan,
                    context=normalized_context,
                )
            )

        if normalized_context.get(
            "run_functional_tests",
            True,
        ):
            checks.append(
                self._run_builtin_check(
                    check_type=ValidationCheckType.FUNCTIONAL,
                    name="Testy funkcjonalne",
                    execution=normalized_execution,
                    plan=normalized_plan,
                    context=normalized_context,
                )
            )

        if self._requires_security_check(
            normalized_plan,
            normalized_context,
        ):
            checks.append(
                self._run_builtin_check(
                    check_type=ValidationCheckType.SECURITY,
                    name="Walidacja bezpieczeństwa",
                    execution=normalized_execution,
                    plan=normalized_plan,
                    context=normalized_context,
                )
            )

        if self._requires_performance_check(
            normalized_plan,
            normalized_context,
        ):
            checks.append(
                self._run_builtin_check(
                    check_type=ValidationCheckType.PERFORMANCE,
                    name="Walidacja wydajności",
                    execution=normalized_execution,
                    plan=normalized_plan,
                    context=normalized_context,
                )
            )

        checks.extend(
            self._run_custom_validators(
                cycle_id=normalized_cycle_id,
                execution=normalized_execution,
                plan=normalized_plan,
                context=normalized_context,
            )
        )

        failed_checks = [
            check.check_type
            for check in checks
            if not check.success
        ]

        errors = self._unique_strings(
            [
                error
                for check in checks
                for error in check.errors
            ]
        )

        warnings = self._unique_strings(
            [
                warning
                for check in checks
                for warning in check.warnings
            ]
        )

        success = self._calculate_success(
            checks
        )

        retry_recommended = (
            not success
            and normalized_attempt
            < self.max_attempts
            and not self._has_critical_failure(
                checks
            )
        )

        rollback_required = (
            not success
            and (
                normalized_attempt
                >= self.max_attempts
                or self._has_critical_failure(
                    checks
                )
                or self._plan_requires_rollback(
                    normalized_plan
                )
            )
        )

        if success:
            status = ValidationLoopStatus.PASSED.value

        elif rollback_required:
            status = (
                ValidationLoopStatus
                .ROLLBACK_REQUIRED
                .value
            )

        elif retry_recommended:
            status = (
                ValidationLoopStatus
                .RETRY_REQUIRED
                .value
            )

        else:
            status = ValidationLoopStatus.FAILED.value

        confidence = self._calculate_confidence(
            checks
        )

        result = ValidationLoopResult(
            validation_id=f"validation_loop_{uuid4().hex}",
            cycle_id=normalized_cycle_id,
            status=status,
            success=success,
            attempt=normalized_attempt,
            max_attempts=self.max_attempts,
            checks=[
                check.to_dict()
                for check in checks
            ],
            failed_checks=failed_checks,
            warnings=warnings,
            errors=errors,
            retry_recommended=retry_recommended,
            rollback_required=rollback_required,
            confidence=confidence,
            metadata={
                "validation_loop_version": "1.0.0",
                "checks_count": len(checks),
                "failed_checks_count": len(
                    failed_checks
                ),
                "require_all_checks": (
                    self.require_all_checks
                ),
            },
        )

        return result.to_dict()

    def run(
        self,
        cycle_id: str,
        execution_result: dict[str, Any],
        plan: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        attempt: int = 1,
    ) -> dict[str, Any]:

        return self.validate(
            cycle_id=cycle_id,
            execution_result=execution_result,
            plan=plan,
            context=context,
            attempt=attempt,
        )

    def _run_builtin_check(
        self,
        check_type: ValidationCheckType,
        name: str,
        execution: dict[str, Any],
        plan: dict[str, Any],
        context: dict[str, Any],
    ) -> ValidationCheckResult:

        validator = self.validators.get(
            check_type.value
        )

        if validator is not None:
            return self._invoke_validator(
                validator=validator,
                check_type=check_type,
                name=name,
                execution=execution,
                plan=plan,
                context=context,
            )

        embedded = self._find_embedded_result(
            execution,
            check_type,
        )

        if embedded is not None:
            return self._result_from_embedded(
                embedded=embedded,
                check_type=check_type,
                name=name,
            )

        default_success = self._default_check_success(
            execution=execution,
            check_type=check_type,
            context=context,
        )

        status = (
            "PASSED"
            if default_success
            else "FAILED"
        )

        message = (
            f"{name} zakończona sukcesem."
            if default_success
            else f"{name} zakończona błędem."
        )

        errors = []

        if not default_success:
            errors.append(
                f"{name} nie przeszła poprawnie."
            )

        return ValidationCheckResult(
            check_id=f"validation_check_{uuid4().hex}",
            check_type=check_type.value,
            name=name,
            success=default_success,
            status=status,
            message=message,
            details={},
            errors=errors,
            warnings=[],
            metadata={
                "source": "default",
            },
        )

    def _run_custom_validators(
        self,
        cycle_id: str,
        execution: dict[str, Any],
        plan: dict[str, Any],
        context: dict[str, Any],
    ) -> list[ValidationCheckResult]:

        results: list[
            ValidationCheckResult
        ] = []

        for name, validator in self.validators.items():
            if name in {
                item.value
                for item in ValidationCheckType
            }:
                continue

            result = self._invoke_validator(
                validator=validator,
                check_type=ValidationCheckType.CUSTOM,
                name=str(name),
                execution=execution,
                plan=plan,
                context={
                    **context,
                    "cycle_id": cycle_id,
                },
            )

            result.metadata[
                "custom_validator_name"
            ] = str(name)

            results.append(result)

        return results

    def _invoke_validator(
        self,
        validator: Any,
        check_type: ValidationCheckType,
        name: str,
        execution: dict[str, Any],
        plan: dict[str, Any],
        context: dict[str, Any],
    ) -> ValidationCheckResult:

        try:
            if hasattr(
                validator,
                "validate",
            ):
                raw_result = validator.validate(
                    execution,
                    plan,
                    context,
                )

            elif hasattr(
                validator,
                "run",
            ):
                raw_result = validator.run(
                    execution,
                    plan,
                    context,
                )

            elif callable(
                validator
            ):
                raw_result = validator(
                    execution,
                    plan,
                    context,
                )

            else:
                return ValidationCheckResult(
                    check_id=(
                        f"validation_check_"
                        f"{uuid4().hex}"
                    ),
                    check_type=check_type.value,
                    name=name,
                    success=False,
                    status="FAILED",
                    message=(
                        "Validator nie posiada "
                        "obsługiwanej metody."
                    ),
                    errors=[
                        "Nieobsługiwany validator."
                    ],
                    warnings=[],
                    details={},
                    metadata={
                        "source": "validator",
                    },
                )

            normalized = self._normalize_result(
                raw_result
            )

            success = self._detect_success(
                normalized
            )

            return ValidationCheckResult(
                check_id=f"validation_check_{uuid4().hex}",
                check_type=check_type.value,
                name=name,
                success=success,
                status=str(
                    normalized.get(
                        "status",
                        (
                            "PASSED"
                            if success
                            else "FAILED"
                        ),
                    )
                ).upper(),
                message=str(
                    normalized.get(
                        "message",
                        (
                            f"{name} zakończona sukcesem."
                            if success
                            else f"{name} zakończona błędem."
                        ),
                    )
                ),
                details=self._safe_dict(
                    normalized.get(
                        "details",
                        normalized,
                    )
                ),
                errors=self._collect_errors(
                    normalized
                ),
                warnings=self._safe_string_list(
                    normalized.get(
                        "warnings",
                        [],
                    )
                ),
                metadata={
                    "source": "validator",
                },
            )

        except Exception as error:
            return ValidationCheckResult(
                check_id=f"validation_check_{uuid4().hex}",
                check_type=check_type.value,
                name=name,
                success=False,
                status="FAILED",
                message=(
                    f"Validator zakończył się wyjątkiem: "
                    f"{type(error).__name__}: {error}"
                ),
                details={},
                errors=[
                    f"{type(error).__name__}: {error}"
                ],
                warnings=[],
                metadata={
                    "source": "validator_exception",
                },
            )

    def _find_embedded_result(
        self,
        execution: dict[str, Any],
        check_type: ValidationCheckType,
    ) -> dict[str, Any] | None:

        mapping = {
            ValidationCheckType.SYNTAX: (
                "syntax_validation",
                "syntax",
            ),
            ValidationCheckType.IMPORTS: (
                "import_validation",
                "imports",
            ),
            ValidationCheckType.UNIT_TESTS: (
                "unit_tests",
                "tests",
            ),
            ValidationCheckType.INTEGRATION_TESTS: (
                "integration_tests",
            ),
            ValidationCheckType.FUNCTIONAL: (
                "functional_tests",
                "functional",
            ),
            ValidationCheckType.SECURITY: (
                "security_validation",
                "security",
            ),
            ValidationCheckType.PERFORMANCE: (
                "performance_validation",
                "performance",
            ),
        }

        validation = execution.get(
            "validation"
        )

        sources = [
            execution,
            validation
            if isinstance(
                validation,
                dict,
            )
            else {},
        ]

        for source in sources:
            for key in mapping.get(
                check_type,
                (),
            ):
                value = source.get(
                    key
                )

                if isinstance(
                    value,
                    dict,
                ):
                    return dict(
                        value
                    )

                if isinstance(
                    value,
                    bool,
                ):
                    return {
                        "success": value,
                        "status": (
                            "PASSED"
                            if value
                            else "FAILED"
                        ),
                    }

        return None

    def _result_from_embedded(
        self,
        embedded: dict[str, Any],
        check_type: ValidationCheckType,
        name: str,
    ) -> ValidationCheckResult:

        success = self._detect_success(
            embedded
        )

        return ValidationCheckResult(
            check_id=f"validation_check_{uuid4().hex}",
            check_type=check_type.value,
            name=name,
            success=success,
            status=str(
                embedded.get(
                    "status",
                    (
                        "PASSED"
                        if success
                        else "FAILED"
                    ),
                )
            ).upper(),
            message=str(
                embedded.get(
                    "message",
                    (
                        f"{name} zakończona sukcesem."
                        if success
                        else f"{name} zakończona błędem."
                    ),
                )
            ),
            details=dict(
                embedded
            ),
            errors=self._collect_errors(
                embedded
            ),
            warnings=self._safe_string_list(
                embedded.get(
                    "warnings",
                    [],
                )
            ),
            metadata={
                "source": "embedded",
            },
        )

    def _default_check_success(
        self,
        execution: dict[str, Any],
        check_type: ValidationCheckType,
        context: dict[str, Any],
    ) -> bool:

        if not self._detect_success(
            execution
        ):
            return False

        strict_checks = self._safe_string_list(
            context.get(
                "strict_checks",
                [],
            )
        )

        if (
            check_type.value
            in strict_checks
        ):
            return False

        return True

    def _calculate_success(
        self,
        checks: list[ValidationCheckResult],
    ) -> bool:

        if not checks:
            return False

        if self.require_all_checks:
            return all(
                check.success
                for check in checks
            )

        passed = sum(
            1
            for check in checks
            if check.success
        )

        return passed >= max(
            1,
            len(checks) // 2 + 1,
        )

    def _has_critical_failure(
        self,
        checks: list[ValidationCheckResult],
    ) -> bool:

        critical_types = {
            ValidationCheckType.SYNTAX.value,
            ValidationCheckType.IMPORTS.value,
            ValidationCheckType.SECURITY.value,
        }

        return any(
            not check.success
            and check.check_type
            in critical_types
            for check in checks
        )

    def _requires_security_check(
        self,
        plan: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:

        if context.get(
            "run_security_validation"
        ) is True:
            return True

        improvement_type = str(
            self._safe_dict(
                plan.get(
                    "metadata",
                    {},
                )
            ).get(
                "improvement_type",
                "",
            )
        ).upper()

        return improvement_type == "SECURITY"

    def _requires_performance_check(
        self,
        plan: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:

        if context.get(
            "run_performance_validation"
        ) is True:
            return True

        improvement_type = str(
            self._safe_dict(
                plan.get(
                    "metadata",
                    {},
                )
            ).get(
                "improvement_type",
                "",
            )
        ).upper()

        return improvement_type == "PERFORMANCE"

    def _plan_requires_rollback(
        self,
        plan: dict[str, Any],
    ) -> bool:

        return bool(
            plan.get(
                "rollback_required",
                False,
            )
        )

    def _calculate_confidence(
        self,
        checks: list[ValidationCheckResult],
    ) -> float:

        if not checks:
            return 0.0

        passed = sum(
            1
            for check in checks
            if check.success
        )

        confidence = passed / len(
            checks
        )

        return round(
            confidence,
            2,
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

        if isinstance(
            result,
            bool,
        ):
            return {
                "success": result,
                "status": (
                    "PASSED"
                    if result
                    else "FAILED"
                ),
            }

        return {
            "success": True,
            "status": "PASSED",
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

        valid = result.get(
            "valid"
        )

        if isinstance(
            valid,
            bool,
        ):
            return valid

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
            "OK",
            "SKIPPED",
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

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
    parse_risk_score,
)


@dataclass(slots=True)
class ExecutionGuardDecision:
    allowed: bool
    status: str
    risk_score: float = 0.0
    risk_level: str = "LOW"
    requires_approval: bool = True
    approval_mode: str = "MANUAL"
    targets: list[str] = field(
        default_factory=list
    )
    reasons: list[str] = field(
        default_factory=list
    )
    errors: list[str] = field(
        default_factory=list
    )
    checks: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionGuard:
    """Final safety gate before any project write."""

    BLOCKED_STATUSES = {
        "PATCH_REJECTED",
        "VALIDATION_FAILED",
        "FAILED",
        "FAILED_AND_ROLLED_BACK",
        "SOURCE_CHANGED",
        "EXECUTION_BLOCKED",
        "TRANSACTION_INVALID",
        "REQUEST_INVALID",
    }

    ALLOWED_RISK_LEVELS = {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }

    def __init__(
        self,
        project_root: str | Path | None = None,
        max_risk_score: float = 65.0,
        *,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self.policy = (
            policy
            or ExecutionPolicy(
                project_root=project_root,
                max_risk_score=max_risk_score,
            )
        )
        self.project_root = self.policy.root
        self.max_risk_score = float(
            self.policy.max_risk_score
        )
        self.boundary = ProjectBoundaryPolicy(
            self.policy
        )
        self.last_decision: (
            ExecutionGuardDecision | None
        ) = None

    def evaluate(
        self,
        *,
        task: dict[str, Any],
        prediction: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
        approved: bool = False,
        automatic: bool = False,
    ) -> ExecutionGuardDecision:
        task = dict(task or {})
        prediction = dict(prediction or {})
        validation = dict(validation or {})

        reasons: list[str] = []
        errors: list[str] = []
        checks: dict[str, Any] = {}

        target_values = self._target_values(
            task
        )
        targets, target_errors = (
            self.boundary.validate_targets(
                target_values,
                require_file=False,
                allow_missing=True,
            )
        )
        errors.extend(
            target_errors
        )
        checks["targets_valid"] = (
            bool(targets)
            and not target_errors
        )

        try:
            risk_score = parse_risk_score(
                prediction.get(
                    "risk_score",
                    prediction.get(
                        "predicted_risk",
                        task.get(
                            "risk_score",
                            0.0,
                        ),
                    ),
                )
            )
        except ValueError as error:
            risk_score = 0.0
            errors.append(
                str(error)
            )

        risk_level = str(
            prediction.get(
                "risk_level",
                task.get(
                    "risk_level",
                    "LOW",
                ),
            )
        ).strip().upper()

        if risk_level not in self.ALLOWED_RISK_LEVELS:
            errors.append(
                "Nieprawidłowy poziom ryzyka."
            )

        if risk_score > self.policy.max_risk_score:
            errors.append(
                "Ryzyko przekracza dozwolony limit."
            )

        if risk_level == "CRITICAL":
            errors.append(
                "Zmiana ma krytyczny poziom ryzyka."
            )

        validation_status = str(
            validation.get(
                "status",
                "",
            )
        ).strip().upper()
        validation_success = validation.get(
            "success"
        )

        checks["validation_present"] = bool(
            validation
        )
        checks["validation_success"] = (
            validation_success is True
        )

        if self.policy.require_validation:
            if not validation:
                errors.append(
                    "Brak wyniku walidacji wykonania."
                )
            elif validation_success is not True:
                errors.append(
                    "Walidacja nie potwierdziła powodzenia."
                )

        if validation_status in self.BLOCKED_STATUSES:
            errors.append(
                "Walidacja zwróciła status blokujący."
            )

        approval_is_explicit = (
            approved is True
        )
        approval_mode = (
            "AUTOMATIC"
            if automatic
            else "MANUAL"
        )
        checks["approval_is_explicit"] = (
            approval_is_explicit
        )
        checks["automatic_approval"] = bool(
            automatic
        )

        if not approval_is_explicit:
            reasons.append(
                "Wymagana jest jawna akceptacja."
            )

        if automatic:
            if not self.policy.allow_auto_approval:
                errors.append(
                    "Polityka blokuje automatyczną akceptację."
                )
            elif (
                risk_score
                > self.policy.max_auto_approval_risk
            ):
                errors.append(
                    "Ryzyko przekracza limit automatycznej "
                    "akceptacji."
                )
            elif risk_level not in {
                "LOW",
                "MEDIUM",
            }:
                errors.append(
                    "Poziom ryzyka nie pozwala na "
                    "automatyczną akceptację."
                )

        allowed = bool(
            not errors
            and approval_is_explicit
        )

        if allowed:
            status = "EXECUTION_ALLOWED"
        elif errors:
            status = "EXECUTION_BLOCKED"
        else:
            status = "WAITING_FOR_APPROVAL"

        decision = ExecutionGuardDecision(
            allowed=allowed,
            status=status,
            risk_score=risk_score,
            risk_level=risk_level,
            requires_approval=True,
            approval_mode=approval_mode,
            targets=[
                str(path)
                for path in targets
            ],
            reasons=reasons,
            errors=self._unique(
                errors
            ),
            checks=checks,
        )
        self.last_decision = decision
        return decision

    def evaluate_transaction(
        self,
        transaction: Any,
        *,
        approved: bool = True,
        automatic: bool = False,
    ) -> ExecutionGuardDecision:
        if transaction is None:
            return self.evaluate(
                task={},
                validation={
                    "success": False,
                    "status": "MISSING_TRANSACTION",
                },
                approved=approved,
                automatic=automatic,
            )

        valid, errors = transaction.validate()
        metadata = dict(
            getattr(
                transaction,
                "metadata",
                {},
            )
            or {}
        )
        decision = self.evaluate(
            task={
                "targets": transaction.files(),
            },
            prediction={
                "risk_score": metadata.get(
                    "risk_score",
                    metadata.get(
                        "predicted_risk",
                        0.0,
                    ),
                ),
                "risk_level": metadata.get(
                    "risk_level",
                    "LOW",
                ),
            },
            validation={
                "success": valid,
                "status": (
                    "VALID"
                    if valid
                    else "TRANSACTION_INVALID"
                ),
                "errors": list(
                    errors
                ),
            },
            approved=approved,
            automatic=automatic,
        )
        metadata["execution_guard"] = (
            decision.to_dict()
        )
        transaction.metadata = metadata
        return decision

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "project_root": str(
                self.project_root
            ),
            "policy": self.policy.to_dict(),
            "last_decision": (
                self.last_decision.to_dict()
                if self.last_decision is not None
                else None
            ),
        }

    @staticmethod
    def _target_values(
        task: dict[str, Any],
    ) -> list[str]:
        values: list[str] = []

        for key in (
            "targets",
            "files",
        ):
            raw = task.get(
                key
            )

            if isinstance(
                raw,
                (
                    list,
                    tuple,
                    set,
                ),
            ):
                values.extend(
                    str(item).strip()
                    for item in raw
                    if str(item).strip()
                )

        for key in (
            "target",
            "path",
        ):
            value = str(
                task.get(
                    key,
                    "",
                )
            ).strip()

            if value:
                values.append(
                    value
                )

        return list(
            dict.fromkeys(
                values
            )
        )

    @staticmethod
    def _unique(
        values: list[str],
    ) -> list[str]:
        return list(
            dict.fromkeys(
                value
                for value in values
                if value
            )
        )

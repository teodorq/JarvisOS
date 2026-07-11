from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ExecutionGuardDecision:
    allowed: bool
    status: str
    risk_score: float = 0.0
    risk_level: str = "LOW"
    requires_approval: bool = True
    reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionGuard:
    """
    Ostatnia bramka bezpieczeństwa przed wykonaniem zmiany.
    """

    BLOCKED_STATUSES = {
        "PATCH_REJECTED",
        "VALIDATION_FAILED",
        "FAILED",
        "FAILED_AND_ROLLED_BACK",
        "SOURCE_CHANGED",
    }

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        max_risk_score: float = 65.0,
    ) -> None:

        self.project_root = Path(
            project_root
        ).resolve()

        self.max_risk_score = float(
            max_risk_score
        )

        self.last_decision: ExecutionGuardDecision | None = None

    def evaluate(
        self,
        *,
        task: dict[str, Any],
        prediction: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
        approved: bool = False,
    ) -> ExecutionGuardDecision:

        task = dict(task or {})
        prediction = dict(prediction or {})
        validation = dict(validation or {})

        reasons: list[str] = []
        errors: list[str] = []

        target = str(
            task.get(
                "target",
                "",
            )
        ).strip()

        if not target:
            errors.append(
                "Brak targetu zadania."
            )
        else:
            try:
                resolved = Path(target).resolve()

                resolved.relative_to(
                    self.project_root
                )

            except ValueError:
                errors.append(
                    "Target znajduje się poza projektem."
                )

        risk_score = float(
            prediction.get(
                "risk_score",
                prediction.get(
                    "predicted_risk",
                    0.0,
                ),
            )
            or 0.0
        )

        risk_level = str(
            prediction.get(
                "risk_level",
                "LOW",
            )
        ).upper()

        validation_status = str(
            validation.get(
                "status",
                "",
            )
        ).upper()

        validation_success = validation.get(
            "success"
        )

        if risk_score > self.max_risk_score:
            errors.append(
                "Ryzyko przekracza dozwolony limit."
            )

        if risk_level == "CRITICAL":
            errors.append(
                "Zmiana ma krytyczny poziom ryzyka."
            )

        if validation_status in self.BLOCKED_STATUSES:
            errors.append(
                "Walidacja zwróciła status blokujący."
            )

        if validation_success is False:
            errors.append(
                "Walidacja zakończyła się niepowodzeniem."
            )

        if not approved:
            reasons.append(
                "Wymagana jest jawna akceptacja."
            )

        allowed = bool(
            not errors
            and approved
        )

        status = (
            "EXECUTION_ALLOWED"
            if allowed
            else (
                "WAITING_FOR_APPROVAL"
                if not errors
                else "EXECUTION_BLOCKED"
            )
        )

        decision = ExecutionGuardDecision(
            allowed=allowed,
            status=status,
            risk_score=risk_score,
            risk_level=risk_level,
            requires_approval=True,
            reasons=reasons,
            errors=errors,
        )

        self.last_decision = decision
        return decision

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": str(self.project_root),
            "max_risk_score": self.max_risk_score,
            "last_decision": (
                self.last_decision.to_dict()
                if self.last_decision is not None
                else None
            ),
        }

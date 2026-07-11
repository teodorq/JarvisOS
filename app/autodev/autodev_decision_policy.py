from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AutoDevDecision:
    allowed: bool
    status: str
    action: str
    requires_approval: bool = True
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutoDevDecisionPolicy:
    """
    Podejmuje bezpieczną decyzję przed uruchomieniem Runtime.
    """

    def __init__(
        self,
        max_risk_score: float = 65.0,
        min_priority_score: float = 0.0,
    ) -> None:
        self.max_risk_score = float(max_risk_score)
        self.min_priority_score = float(
            min_priority_score
        )
        self.last_decision: AutoDevDecision | None = None

    def decide(
        self,
        goal: dict[str, Any],
    ) -> AutoDevDecision:

        risk_score = self._float(
            goal.get(
                "risk_score",
                0.0,
            )
        )

        priority_score = self._float(
            goal.get(
                "priority_score",
                0.0,
            )
        )

        reasons: list[str] = []

        if risk_score > self.max_risk_score:
            decision = AutoDevDecision(
                allowed=False,
                status="RISK_BLOCKED",
                action="ANALYZE_ONLY",
                reasons=[
                    "Ryzyko przekracza dozwolony limit."
                ],
            )
            return self._finish(decision)

        if priority_score < self.min_priority_score:
            decision = AutoDevDecision(
                allowed=False,
                status="LOW_PRIORITY",
                action="DEFER",
                reasons=[
                    "Priorytet jest zbyt niski."
                ],
            )
            return self._finish(decision)

        reasons.append(
            "Cel spełnia wymagania bezpiecznego preview."
        )

        decision = AutoDevDecision(
            allowed=True,
            status="PREVIEW_ALLOWED",
            action="QUEUE_AND_PREVIEW",
            requires_approval=True,
            reasons=reasons,
        )

        return self._finish(decision)

    def _finish(
        self,
        decision: AutoDevDecision,
    ) -> AutoDevDecision:
        self.last_decision = decision
        return decision

    def _float(
        self,
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def status(self) -> dict[str, Any]:
        return {
            "max_risk_score": self.max_risk_score,
            "min_priority_score": (
                self.min_priority_score
            ),
            "last_decision": (
                self.last_decision.to_dict()
                if self.last_decision is not None
                else None
            ),
        }

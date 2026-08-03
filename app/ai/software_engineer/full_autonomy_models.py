from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class FullAutonomyPlan:
    goal_id: str
    portfolio_id: str
    objective: str
    target_files: list[str]
    subsystems: list[str]
    campaigns: list[dict[str, Any]]
    execution_order: list[str]
    acceptance_criteria: list[str]
    fingerprint: str
    estimated_roi: float
    estimated_risk: float
    estimated_minutes: int
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> "FullAutonomyPlan":
        return cls(
            goal_id=str(value.get("goal_id", "")),
            portfolio_id=str(value.get("portfolio_id", "")),
            objective=str(value.get("objective", "")),
            target_files=[
                str(item)
                for item in value.get("target_files", [])
            ],
            subsystems=[
                str(item)
                for item in value.get("subsystems", [])
            ],
            campaigns=[
                dict(item)
                for item in value.get("campaigns", [])
                if isinstance(item, dict)
            ],
            execution_order=[
                str(item)
                for item in value.get("execution_order", [])
            ],
            acceptance_criteria=[
                str(item)
                for item in value.get("acceptance_criteria", [])
            ],
            fingerprint=str(value.get("fingerprint", "")),
            estimated_roi=float(value.get("estimated_roi", 0.0) or 0.0),
            estimated_risk=float(value.get("estimated_risk", 0.0) or 0.0),
            estimated_minutes=int(value.get("estimated_minutes", 0) or 0),
            confidence=float(value.get("confidence", 0.0) or 0.0),
            metadata=dict(value.get("metadata", {}) or {}),
        )

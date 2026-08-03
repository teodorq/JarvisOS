from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


STRATEGIC_ACTIVE_STATES = {
    "ACTIVE",
    "WAITING_APPROVAL",
    "WAITING_RESOURCES",
}
STRATEGIC_TERMINAL_STATES = {
    "COMPLETED",
    "PARTIAL",
    "BLOCKED",
    "REJECTED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class StrategicDevelopmentGoal:
    goal_id: str
    fingerprint: str
    title: str
    objective: str
    subsystem: str
    issue_type: str
    opportunity_ids: list[str] = field(default_factory=list)
    status: str = "PENDING"
    priority_score: float = 0.0
    value_score: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.0
    total_count: int = 0
    pending_count: int = 0
    active_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    rejected_count: int = 0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> "StrategicDevelopmentGoal":
        source = dict(value or {})
        allowed = {
            item.name
            for item in cls.__dataclass_fields__.values()
        }
        filtered = {
            key: source[key]
            for key in allowed
            if key in source
        }
        item = cls(**filtered)
        item.goal_id = str(item.goal_id).strip()
        item.fingerprint = str(item.fingerprint).strip()
        item.title = str(item.title).strip()
        item.objective = str(item.objective).strip()
        item.subsystem = str(item.subsystem).strip()
        item.issue_type = str(item.issue_type).upper().strip()
        item.status = str(item.status).upper().strip() or "PENDING"
        item.opportunity_ids = [
            str(opportunity_id).strip()
            for opportunity_id in item.opportunity_ids
            if str(opportunity_id).strip()
        ][:1000]
        item.priority_score = float(item.priority_score or 0.0)
        item.value_score = float(item.value_score or 0.0)
        item.risk_score = float(item.risk_score or 0.0)
        item.confidence = min(
            1.0,
            max(0.0, float(item.confidence or 0.0)),
        )
        for field_name in (
            "total_count",
            "pending_count",
            "active_count",
            "completed_count",
            "failed_count",
            "rejected_count",
        ):
            setattr(
                item,
                field_name,
                max(0, int(getattr(item, field_name) or 0)),
            )
        item.metadata = dict(item.metadata or {})
        return item


@dataclass(slots=True)
class StrategicDevelopmentPolicy:
    refresh_interval_seconds: float = 300.0
    max_goals: int = 100
    max_active_goals: int = 1
    min_goal_score: float = 15.0
    max_goal_risk: float = 65.0
    min_goal_confidence: float = 0.30
    auto_select: bool = True
    integrate_with_b56: bool = True
    start_b56_with_supervisor: bool = True
    auto_approve: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["auto_approve"] = False
        return value

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any] | None,
    ) -> "StrategicDevelopmentPolicy":
        source = dict(value or {})
        return cls(
            refresh_interval_seconds=min(
                86400.0,
                max(
                    60.0,
                    float(source.get("refresh_interval_seconds", 300.0)),
                ),
            ),
            max_goals=min(
                500,
                max(10, int(source.get("max_goals", 100))),
            ),
            max_active_goals=1,
            min_goal_score=min(
                100.0,
                max(0.0, float(source.get("min_goal_score", 15.0))),
            ),
            max_goal_risk=min(
                100.0,
                max(0.0, float(source.get("max_goal_risk", 65.0))),
            ),
            min_goal_confidence=min(
                1.0,
                max(
                    0.0,
                    float(source.get("min_goal_confidence", 0.30)),
                ),
            ),
            auto_select=bool(source.get("auto_select", True)),
            integrate_with_b56=bool(
                source.get("integrate_with_b56", True)
            ),
            start_b56_with_supervisor=bool(
                source.get("start_b56_with_supervisor", True)
            ),
            auto_approve=False,
        )

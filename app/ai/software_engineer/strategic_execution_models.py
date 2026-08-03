from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


ACTIVE_STRATEGIC_EXECUTION_STATES = {
    "DISPATCHED",
    "QUEUED",
    "SCHEDULED",
    "WAITING_RESOURCES",
    "WAITING_APPROVAL",
    "RECOVERING",
    "RUNNING",
    "PAUSED",
}

TERMINAL_STRATEGIC_EXECUTION_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "DEFERRED_CONSTRAINTS",
    "REJECTED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class StrategicExecutionRecord:
    goal_id: str
    opportunity_id: str
    job_id: str
    execution_id: str = field(
        default_factory=lambda: f"strategic-exec-{uuid4().hex}"
    )
    status: str = "DISPATCHED"
    target: str = ""
    objective: str = ""
    outcome_category: str = ""
    last_error: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str = ""
    observed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> "StrategicExecutionRecord":
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
        item.execution_id = str(item.execution_id).strip()
        item.goal_id = str(item.goal_id).strip()
        item.opportunity_id = str(item.opportunity_id).strip()
        item.job_id = str(item.job_id).strip()
        item.status = str(item.status).upper().strip() or "DISPATCHED"
        item.target = str(item.target).strip()
        item.objective = str(item.objective).strip()
        item.outcome_category = str(item.outcome_category).upper().strip()
        item.last_error = str(item.last_error)
        item.metadata = dict(item.metadata or {})
        return item


@dataclass(slots=True)
class StrategicExecutionPolicy:
    enabled: bool = True
    max_active_executions: int = 1
    max_records: int = 2000
    max_history: int = 1000
    integrate_with_b57: bool = True
    integrate_with_b56: bool = True
    learn_from_deferred: bool = True
    auto_refresh_roadmap: bool = True
    auto_approve: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["max_active_executions"] = 1
        value["auto_approve"] = False
        return value

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any] | None,
    ) -> "StrategicExecutionPolicy":
        source = dict(value or {})
        return cls(
            enabled=bool(source.get("enabled", True)),
            max_active_executions=1,
            max_records=min(
                10000,
                max(100, int(source.get("max_records", 2000))),
            ),
            max_history=min(
                5000,
                max(100, int(source.get("max_history", 1000))),
            ),
            integrate_with_b57=bool(
                source.get("integrate_with_b57", True)
            ),
            integrate_with_b56=bool(
                source.get("integrate_with_b56", True)
            ),
            learn_from_deferred=bool(
                source.get("learn_from_deferred", True)
            ),
            auto_refresh_roadmap=bool(
                source.get("auto_refresh_roadmap", True)
            ),
            auto_approve=False,
        )

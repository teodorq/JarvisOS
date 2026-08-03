from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


TERMINAL_JOB_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
}

ACTIVE_JOB_STATES = {
    "QUEUED",
    "SCHEDULED",
    "WAITING_RESOURCES",
    "WAITING_APPROVAL",
    "RECOVERING",
    "RUNNING",
    "PAUSED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class LongRunningJob:
    objective: str
    job_id: str = field(
        default_factory=lambda: f"longrun-{uuid4().hex}"
    )
    state: str = "QUEUED"
    priority: int = 50
    schedule: dict[str, Any] = field(default_factory=dict)
    execution_context: dict[str, Any] = field(default_factory=dict)
    resource_policy: dict[str, Any] = field(default_factory=dict)
    restart_policy: str = "RESUME"
    max_attempts: int = 3
    attempts: int = 0
    autonomy_run_id: str = ""
    next_run_at: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    started_at: str = ""
    completed_at: str = ""
    heartbeat_at: str = ""
    last_error: str = ""
    last_result: dict[str, Any] = field(default_factory=dict)
    run_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "objective": self.objective,
            "state": self.state,
            "priority": self.priority,
            "schedule": dict(self.schedule),
            "execution_context": dict(self.execution_context),
            "resource_policy": dict(self.resource_policy),
            "restart_policy": self.restart_policy,
            "max_attempts": self.max_attempts,
            "attempts": self.attempts,
            "autonomy_run_id": self.autonomy_run_id,
            "next_run_at": self.next_run_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "heartbeat_at": self.heartbeat_at,
            "last_error": self.last_error,
            "last_result": dict(self.last_result),
            "run_history": [
                dict(item)
                for item in self.run_history
                if isinstance(item, dict)
            ],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LongRunningJob":
        return cls(
            objective=str(value.get("objective", "")).strip(),
            job_id=str(value.get("job_id", "")).strip()
            or f"longrun-{uuid4().hex}",
            state=str(value.get("state", "QUEUED")).upper(),
            priority=_bounded_int(
                value.get("priority", 50),
                minimum=0,
                maximum=100,
            ),
            schedule=_mapping(value.get("schedule")),
            execution_context=_mapping(
                value.get("execution_context")
            ),
            resource_policy=_mapping(
                value.get("resource_policy")
            ),
            restart_policy=str(
                value.get("restart_policy", "RESUME")
            ).upper(),
            max_attempts=_bounded_int(
                value.get("max_attempts", 3),
                minimum=1,
                maximum=10,
            ),
            attempts=_bounded_int(
                value.get("attempts", 0),
                minimum=0,
                maximum=10_000,
            ),
            autonomy_run_id=str(
                value.get("autonomy_run_id", "")
            ).strip(),
            next_run_at=str(value.get("next_run_at", "")),
            created_at=str(value.get("created_at", "")) or utc_now(),
            updated_at=str(value.get("updated_at", "")) or utc_now(),
            started_at=str(value.get("started_at", "")),
            completed_at=str(value.get("completed_at", "")),
            heartbeat_at=str(value.get("heartbeat_at", "")),
            last_error=str(value.get("last_error", "")),
            last_result=_mapping(value.get("last_result")),
            run_history=[
                dict(item)
                for item in value.get("run_history", [])
                if isinstance(item, dict)
            ][-50:],
            metadata=_mapping(value.get("metadata")),
        )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _bounded_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return min(maximum, max(minimum, parsed))

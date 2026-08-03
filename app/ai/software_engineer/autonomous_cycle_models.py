from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AutonomousBacklogPolicy:
    """Hard limits for one approval-gated autonomous backlog cycle."""

    max_candidates: int = 50
    max_attempts_per_cycle: int = 6
    max_risk_score: float = 50.0
    min_confidence: float = 0.75
    min_final_score: float = 15.0
    lease_seconds: int = 1800
    max_cycles: int = 40
    allowed_statuses: tuple[str, ...] = ("PENDING", "QUEUED", "READY", "RETRY")
    allowed_prefixes: tuple[str, ...] = ("app/",)
    protected_fragments: tuple[str, ...] = (
        "/.git/", "/.venv/", "/archive/", "/data/", "/tests/", "/config/",
    )
    auto_approve: bool = False
    auto_deploy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AutonomousBacklogCandidate:
    source: str
    task_id: str
    fingerprint: str
    target: str
    title: str
    description: str
    issue_type: str
    status: str
    risk_score: float
    value_score: float
    effort_score: float
    confidence: float
    final_score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutonomousDevelopmentCycle:
    cycle_id: str
    status: str
    created_at: str
    updated_at: str
    task: dict[str, Any] = field(default_factory=dict)
    task_fingerprint: str = ""
    lease_expires_at: str = ""
    safe_session_id: str = ""
    operation_fingerprint: str = ""
    attempted_task_ids: list[str] = field(default_factory=list)
    deferred: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AutonomousDevelopmentCycle":
        return cls(
            cycle_id=str(value.get("cycle_id", "")),
            status=str(value.get("status", "")),
            created_at=str(value.get("created_at", "")),
            updated_at=str(value.get("updated_at", "")),
            task=dict(value.get("task", {}) or {}),
            task_fingerprint=str(value.get("task_fingerprint", "")),
            lease_expires_at=str(value.get("lease_expires_at", "")),
            safe_session_id=str(value.get("safe_session_id", "")),
            operation_fingerprint=str(value.get("operation_fingerprint", "")),
            attempted_task_ids=list(value.get("attempted_task_ids", []) or []),
            deferred=list(value.get("deferred", []) or []),
            errors=list(value.get("errors", []) or []),
            result=dict(value.get("result", {}) or {}),
        )

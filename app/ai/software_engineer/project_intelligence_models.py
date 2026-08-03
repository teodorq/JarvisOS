from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


ACTIVE_OPPORTUNITY_STATES = {
    "DISPATCHED",
    "RUNNING",
    "WAITING_APPROVAL",
    "WAITING_RESOURCES",
}
TERMINAL_OPPORTUNITY_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "REJECTED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ProjectOpportunity:
    opportunity_id: str = field(
        default_factory=lambda: f"opportunity-{uuid.uuid4().hex}"
    )
    title: str = ""
    objective: str = ""
    target: str = ""
    source: str = "B55ProjectIntelligence"
    severity: str = "MEDIUM"
    issue_type: str = "PROJECT_IMPROVEMENT"
    fingerprint: str = ""
    value_score: float = 0.0
    risk_score: float = 0.0
    effort_score: float = 0.0
    confidence: float = 0.5
    final_score: float = 0.0
    status: str = "PENDING"
    job_id: str = ""
    attempts: int = 0
    last_error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    dispatched_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> "ProjectOpportunity":
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
        item.severity = str(item.severity).upper()
        item.status = str(item.status).upper()
        item.value_score = float(item.value_score or 0.0)
        item.risk_score = float(item.risk_score or 0.0)
        item.effort_score = float(item.effort_score or 0.0)
        item.confidence = min(1.0, max(0.0, float(item.confidence or 0.0)))
        item.final_score = float(item.final_score or 0.0)
        item.attempts = max(0, int(item.attempts or 0))
        item.metadata = dict(item.metadata or {})
        return item


@dataclass(slots=True)
class ProjectIntelligencePolicy:
    scan_interval_seconds: float = 300.0
    max_dispatch_per_cycle: int = 1
    max_active_jobs: int = 1
    max_backlog: int = 200
    min_score: float = 25.0
    max_risk: float = 65.0
    min_confidence: float = 0.30
    auto_dispatch: bool = False
    auto_approve: bool = False
    auto_rollback: bool = True
    final_validation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any] | None,
    ) -> "ProjectIntelligencePolicy":
        source = dict(value or {})
        policy = cls(
            scan_interval_seconds=min(
                86400.0,
                max(30.0, float(source.get("scan_interval_seconds", 300.0))),
            ),
            max_dispatch_per_cycle=min(
                3,
                max(1, int(source.get("max_dispatch_per_cycle", 1))),
            ),
            max_active_jobs=min(
                3,
                max(1, int(source.get("max_active_jobs", 1))),
            ),
            max_backlog=min(
                1000,
                max(20, int(source.get("max_backlog", 200))),
            ),
            min_score=min(
                100.0,
                max(0.0, float(source.get("min_score", 25.0))),
            ),
            max_risk=min(
                100.0,
                max(0.0, float(source.get("max_risk", 65.0))),
            ),
            min_confidence=min(
                1.0,
                max(0.0, float(source.get("min_confidence", 0.30))),
            ),
            auto_dispatch=bool(source.get("auto_dispatch", False)),
            auto_approve=False,
            auto_rollback=bool(source.get("auto_rollback", True)),
            final_validation=bool(source.get("final_validation", True)),
        )
        return policy

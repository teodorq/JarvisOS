from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


CAMPAIGN_TERMINAL = {
    "READY_FOR_APPROVAL",
    "REVIEW_COMPLETED",
    "NO_PREPARABLE_TASK",
    "FAILED",
    "CANCELLED",
    "SAFETY_VIOLATION",
}
CAMPAIGN_ACTIVE = {"CREATED", "RUNNING", "RECOVERING", "CANCELLING"}


@dataclass(frozen=True, slots=True)
class AutonomousWorkPolicy:
    max_tasks: int = 5
    max_seed_candidates: int = 10
    max_failures: int = 2
    max_runtime_seconds: int = 3600
    lease_seconds: int = 120
    max_campaigns: int = 30
    max_risk_score: float = 50.0
    min_confidence: float = 0.75
    max_changed_files_per_patch: int = 1
    max_changed_lines_per_patch: int = 40
    auto_approve: bool = False
    auto_deploy: bool = False

    def bounded_tasks(self, requested: int | None) -> int:
        value = self.max_tasks if requested is None else int(requested)
        return max(1, min(self.max_tasks, value))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutonomousWorkCampaign:
    campaign_id: str
    status: str
    created_at: str
    updated_at: str
    requested_tasks: int
    prepared_tasks: int = 0
    failed_tasks: int = 0
    current_task_fingerprint: str = ""
    attempted_fingerprints: list[str] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    prepared_session_ids: list[str] = field(default_factory=list)
    seeded_task_ids: list[str] = field(default_factory=list)
    stop_requested: bool = False
    lease_token: str = ""
    lease_expires_at: str = ""
    source_digest_before: str = ""
    source_digest_after: str = ""
    risk_summary: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    recovery_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AutonomousWorkCampaign":
        return cls(
            campaign_id=str(value.get("campaign_id", "")),
            status=str(value.get("status", "CREATED")),
            created_at=str(value.get("created_at", "")),
            updated_at=str(value.get("updated_at", "")),
            requested_tasks=max(1, int(value.get("requested_tasks", 1) or 1)),
            prepared_tasks=int(value.get("prepared_tasks", 0) or 0),
            failed_tasks=int(value.get("failed_tasks", 0) or 0),
            current_task_fingerprint=str(value.get("current_task_fingerprint", "")),
            attempted_fingerprints=list(value.get("attempted_fingerprints", []) or []),
            items=list(value.get("items", []) or []),
            events=list(value.get("events", []) or []),
            prepared_session_ids=list(value.get("prepared_session_ids", []) or []),
            seeded_task_ids=list(value.get("seeded_task_ids", []) or []),
            stop_requested=bool(value.get("stop_requested", False)),
            lease_token=str(value.get("lease_token", "")),
            lease_expires_at=str(value.get("lease_expires_at", "")),
            source_digest_before=str(value.get("source_digest_before", "")),
            source_digest_after=str(value.get("source_digest_after", "")),
            risk_summary=dict(value.get("risk_summary", {}) or {}),
            errors=list(value.get("errors", []) or []),
            recovery_count=int(value.get("recovery_count", 0) or 0),
        )

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .change_campaign_models import utc_now


@dataclass(slots=True)
class ManagedCampaign:
    campaign_id: str
    objective: str
    stages: list[dict[str, Any]]
    targets: list[str]
    priority: str = "NORMAL"
    priority_score: int = 50
    depends_on: list[str] = field(default_factory=list)
    status: str = "PENDING"
    attempt_count: int = 0
    started_at: str = ""
    completed_at: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.status in {
            "COMPLETED",
            "FAILED",
            "ROLLED_BACK",
            "BLOCKED",
            "CANCELLED",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "objective": self.objective,
            "stages": [dict(item) for item in self.stages],
            "targets": list(self.targets),
            "priority": self.priority,
            "priority_score": self.priority_score,
            "depends_on": list(self.depends_on),
            "status": self.status,
            "attempt_count": self.attempt_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": dict(self.result),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ManagedCampaign":
        return cls(
            campaign_id=str(value.get("campaign_id", "")),
            objective=str(value.get("objective", "")),
            stages=[
                dict(item)
                for item in value.get("stages", [])
                if isinstance(item, dict)
            ],
            targets=[str(item) for item in value.get("targets", [])],
            priority=str(value.get("priority", "NORMAL")).upper(),
            priority_score=max(0, min(100, int(value.get("priority_score", 50) or 50))),
            depends_on=[str(item) for item in value.get("depends_on", [])],
            status=str(value.get("status", "PENDING")).upper(),
            attempt_count=max(0, int(value.get("attempt_count", 0) or 0)),
            started_at=str(value.get("started_at", "")),
            completed_at=str(value.get("completed_at", "")),
            result=dict(value.get("result", {}) or {}),
            errors=[str(item) for item in value.get("errors", [])],
            warnings=[str(item) for item in value.get("warnings", [])],
            metadata=dict(value.get("metadata", {}) or {}),
        )


@dataclass(slots=True)
class MultiCampaignPortfolio:
    portfolio_id: str
    objective: str
    campaigns: list[ManagedCampaign]
    execution_order: list[str]
    fingerprint: str
    status: str = "PLANNED"
    current_campaign_id: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str = ""
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    final_validation: dict[str, Any] = field(default_factory=dict)
    rollback: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def completed_campaign_ids(self) -> list[str]:
        return [
            item.campaign_id
            for item in self.campaigns
            if item.status == "COMPLETED"
        ]

    @property
    def pending_campaign_ids(self) -> list[str]:
        return [
            item.campaign_id
            for item in self.campaigns
            if item.status in {"PENDING", "PAUSED", "RUNNING"}
        ]

    @property
    def failed_campaign_ids(self) -> list[str]:
        return [
            item.campaign_id
            for item in self.campaigns
            if item.status == "FAILED"
        ]

    @property
    def blocked_campaign_ids(self) -> list[str]:
        return [
            item.campaign_id
            for item in self.campaigns
            if item.status == "BLOCKED"
        ]

    def campaign(self, campaign_id: str) -> ManagedCampaign:
        for item in self.campaigns:
            if item.campaign_id == campaign_id:
                return item
        raise KeyError(f"Nie znaleziono kampanii: {campaign_id}")

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "objective": self.objective,
            "status": self.status,
            "current_campaign_id": self.current_campaign_id,
            "execution_order": list(self.execution_order),
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "campaigns": [item.to_dict() for item in self.campaigns],
            "completed_campaign_ids": self.completed_campaign_ids,
            "pending_campaign_ids": self.pending_campaign_ids,
            "failed_campaign_ids": self.failed_campaign_ids,
            "blocked_campaign_ids": self.blocked_campaign_ids,
            "checkpoints": [dict(item) for item in self.checkpoints],
            "final_validation": dict(self.final_validation),
            "rollback": dict(self.rollback),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MultiCampaignPortfolio":
        return cls(
            portfolio_id=str(value.get("portfolio_id", "")),
            objective=str(value.get("objective", "")),
            campaigns=[
                ManagedCampaign.from_dict(item)
                for item in value.get("campaigns", [])
                if isinstance(item, dict)
            ],
            execution_order=[str(item) for item in value.get("execution_order", [])],
            fingerprint=str(value.get("fingerprint", "")),
            status=str(value.get("status", "PLANNED")).upper(),
            current_campaign_id=str(value.get("current_campaign_id", "")),
            created_at=str(value.get("created_at", "") or utc_now()),
            updated_at=str(value.get("updated_at", "") or utc_now()),
            completed_at=str(value.get("completed_at", "")),
            checkpoints=[
                dict(item)
                for item in value.get("checkpoints", [])
                if isinstance(item, dict)
            ],
            final_validation=dict(value.get("final_validation", {}) or {}),
            rollback=dict(value.get("rollback", {}) or {}),
            warnings=[str(item) for item in value.get("warnings", [])],
            errors=[str(item) for item in value.get("errors", [])],
            metadata=dict(value.get("metadata", {}) or {}),
        )

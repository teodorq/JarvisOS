from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


STRATEGIC_PORTFOLIO_ACTIVE_STATES = {
    "ACTIVE",
    "WAITING_APPROVAL",
}

STRATEGIC_PORTFOLIO_TERMINAL_STATES = {
    "BLOCKED",
    "COMPLETED",
    "REJECTED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class StrategicPortfolioEntry:
    goal_id: str
    subsystem: str
    issue_type: str
    title: str = ""
    status: str = "READY"
    base_priority_score: float = 0.0
    adaptive_priority_score: float = 0.0
    value_score: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.0
    pending_count: int = 0
    executions_total: int = 0
    active_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    deferred_count: int = 0
    waiting_approval_count: int = 0
    consecutive_failures: int = 0
    consecutive_deferred: int = 0
    success_rate: float = 0.0
    last_execution_id: str = ""
    last_outcome: str = ""
    cooldown_until: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
    ) -> "StrategicPortfolioEntry":
        source = dict(value or {})
        allowed = {
            item.name
            for item in cls.__dataclass_fields__.values()
        }
        item = cls(**{
            key: source[key]
            for key in allowed
            if key in source
        })
        item.goal_id = str(item.goal_id).strip()
        item.subsystem = str(item.subsystem).strip()
        item.issue_type = str(item.issue_type).upper().strip()
        item.title = str(item.title).strip()
        item.status = str(item.status).upper().strip() or "READY"
        for field_name in (
            "base_priority_score",
            "adaptive_priority_score",
            "value_score",
            "risk_score",
            "success_rate",
        ):
            setattr(item, field_name, float(getattr(item, field_name) or 0.0))
        item.confidence = min(
            1.0,
            max(0.0, float(item.confidence or 0.0)),
        )
        for field_name in (
            "pending_count",
            "executions_total",
            "active_count",
            "completed_count",
            "failed_count",
            "deferred_count",
            "waiting_approval_count",
            "consecutive_failures",
            "consecutive_deferred",
        ):
            setattr(
                item,
                field_name,
                max(0, int(getattr(item, field_name) or 0)),
            )
        item.last_execution_id = str(item.last_execution_id).strip()
        item.last_outcome = str(item.last_outcome).upper().strip()
        item.cooldown_until = str(item.cooldown_until).strip()
        item.metadata = dict(item.metadata or {})
        return item


@dataclass(slots=True)
class StrategicPortfolioPolicy:
    enabled: bool = True
    rebalance_interval_seconds: float = 300.0
    max_entries: int = 200
    max_active_goals: int = 1
    min_adaptive_score: float = 5.0
    failure_cooldown_threshold: int = 2
    deferred_cooldown_threshold: int = 3
    cooldown_seconds: float = 900.0
    exploration_bonus: float = 6.0
    completion_bonus: float = 2.0
    failure_penalty: float = 8.0
    deferred_penalty: float = 1.5
    diversity_penalty: float = 8.0
    integrate_with_b57: bool = True
    integrate_with_b58: bool = True
    start_b58_with_supervisor: bool = True
    auto_apply_selection: bool = True
    auto_approve: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["max_active_goals"] = 1
        value["auto_approve"] = False
        return value

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any] | None,
    ) -> "StrategicPortfolioPolicy":
        source = dict(value or {})
        return cls(
            enabled=bool(source.get("enabled", True)),
            rebalance_interval_seconds=min(
                86400.0,
                max(
                    60.0,
                    float(source.get("rebalance_interval_seconds", 300.0)),
                ),
            ),
            max_entries=min(
                1000,
                max(10, int(source.get("max_entries", 200))),
            ),
            max_active_goals=1,
            min_adaptive_score=min(
                100.0,
                max(
                    -100.0,
                    float(source.get("min_adaptive_score", 5.0)),
                ),
            ),
            failure_cooldown_threshold=min(
                20,
                max(
                    1,
                    int(source.get("failure_cooldown_threshold", 2)),
                ),
            ),
            deferred_cooldown_threshold=min(
                50,
                max(
                    1,
                    int(source.get("deferred_cooldown_threshold", 3)),
                ),
            ),
            cooldown_seconds=min(
                86400.0,
                max(60.0, float(source.get("cooldown_seconds", 900.0))),
            ),
            exploration_bonus=cls._bounded(
                source.get("exploration_bonus", 6.0),
                0.0,
                30.0,
            ),
            completion_bonus=cls._bounded(
                source.get("completion_bonus", 2.0),
                0.0,
                20.0,
            ),
            failure_penalty=cls._bounded(
                source.get("failure_penalty", 8.0),
                0.0,
                30.0,
            ),
            deferred_penalty=cls._bounded(
                source.get("deferred_penalty", 1.5),
                0.0,
                20.0,
            ),
            diversity_penalty=cls._bounded(
                source.get("diversity_penalty", 8.0),
                0.0,
                30.0,
            ),
            integrate_with_b57=bool(
                source.get("integrate_with_b57", True)
            ),
            integrate_with_b58=bool(
                source.get("integrate_with_b58", True)
            ),
            start_b58_with_supervisor=bool(
                source.get("start_b58_with_supervisor", True)
            ),
            auto_apply_selection=bool(
                source.get("auto_apply_selection", True)
            ),
            auto_approve=False,
        )

    @staticmethod
    def _bounded(value: Any, minimum: float, maximum: float) -> float:
        return min(maximum, max(minimum, float(value or 0.0)))

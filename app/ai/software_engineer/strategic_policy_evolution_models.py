from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SAFE_PORTFOLIO_POLICY_FIELDS = {
    "rebalance_interval_seconds",
    "min_adaptive_score",
    "failure_cooldown_threshold",
    "deferred_cooldown_threshold",
    "cooldown_seconds",
    "exploration_bonus",
    "completion_bonus",
    "failure_penalty",
    "deferred_penalty",
    "diversity_penalty",
}


@dataclass(slots=True)
class StrategicPolicyEvolutionPolicy:
    enabled: bool = True
    learning_interval_seconds: float = 300.0
    observation_window: int = 200
    min_observations: int = 3
    min_confidence: float = 0.45
    max_history: int = 1000
    max_revisions: int = 100
    max_score_step: float = 1.0
    max_penalty_step: float = 1.0
    max_bonus_step: float = 0.75
    max_cooldown_ratio_step: float = 0.15
    auto_apply_safe_changes: bool = True
    integrate_with_b58: bool = True
    integrate_with_b59: bool = True
    start_b59_with_supervisor: bool = True
    auto_approve: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["auto_approve"] = False
        return value

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any] | None,
    ) -> "StrategicPolicyEvolutionPolicy":
        source = dict(value or {})
        return cls(
            enabled=bool(source.get("enabled", True)),
            learning_interval_seconds=cls._bounded(
                source.get("learning_interval_seconds", 300.0),
                60.0,
                86400.0,
            ),
            observation_window=int(cls._bounded(
                source.get("observation_window", 200), 10, 5000
            )),
            min_observations=int(cls._bounded(
                source.get("min_observations", 3), 1, 1000
            )),
            min_confidence=cls._bounded(
                source.get("min_confidence", 0.45), 0.1, 1.0
            ),
            max_history=int(cls._bounded(
                source.get("max_history", 1000), 100, 5000
            )),
            max_revisions=int(cls._bounded(
                source.get("max_revisions", 100), 10, 1000
            )),
            max_score_step=cls._bounded(
                source.get("max_score_step", 1.0), 0.1, 5.0
            ),
            max_penalty_step=cls._bounded(
                source.get("max_penalty_step", 1.0), 0.1, 5.0
            ),
            max_bonus_step=cls._bounded(
                source.get("max_bonus_step", 0.75), 0.1, 5.0
            ),
            max_cooldown_ratio_step=cls._bounded(
                source.get("max_cooldown_ratio_step", 0.15), 0.01, 0.5
            ),
            auto_apply_safe_changes=bool(
                source.get("auto_apply_safe_changes", True)
            ),
            integrate_with_b58=bool(source.get("integrate_with_b58", True)),
            integrate_with_b59=bool(source.get("integrate_with_b59", True)),
            start_b59_with_supervisor=bool(
                source.get("start_b59_with_supervisor", True)
            ),
            auto_approve=False,
        )

    @staticmethod
    def _bounded(value: Any, minimum: float, maximum: float) -> float:
        return min(maximum, max(minimum, float(value or 0.0)))


@dataclass(slots=True)
class StrategicLearningMetrics:
    observations: int = 0
    completed: int = 0
    failed: int = 0
    deferred: int = 0
    waiting_approval: int = 0
    cancelled: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    deferred_rate: float = 0.0
    approval_rate: float = 0.0
    subsystem_count: int = 0
    subsystem_concentration: float = 0.0
    portfolio_ready: int = 0
    portfolio_cooldown: int = 0
    average_adaptive_score: float = 0.0
    evidence_from: str = ""
    evidence_to: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "StrategicLearningMetrics":
        source = dict(value or {})
        allowed = {item.name for item in cls.__dataclass_fields__.values()}
        item = cls(**{key: source[key] for key in allowed if key in source})
        for name in (
            "observations", "completed", "failed", "deferred",
            "waiting_approval", "cancelled", "subsystem_count",
            "portfolio_ready", "portfolio_cooldown",
        ):
            setattr(item, name, max(0, int(getattr(item, name) or 0)))
        for name in (
            "success_rate", "failure_rate", "deferred_rate",
            "approval_rate", "subsystem_concentration",
            "average_adaptive_score",
        ):
            setattr(item, name, float(getattr(item, name) or 0.0))
        return item


@dataclass(slots=True)
class StrategicPolicyRevision:
    policy: dict[str, Any]
    changes: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    revision_id: str = field(
        default_factory=lambda: f"policy-revision-{uuid4().hex}"
    )
    parent_revision_id: str = ""
    status: str = "PROPOSED"
    reason: str = ""
    evidence_count: int = 0
    confidence: float = 0.0
    created_at: str = field(default_factory=utc_now)
    applied_at: str = ""
    rolled_back_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["policy"] = {
            key: item
            for key, item in dict(value.get("policy", {})).items()
            if key in SAFE_PORTFOLIO_POLICY_FIELDS
            or key in {"max_active_goals", "auto_approve"}
        }
        value["policy"]["max_active_goals"] = 1
        value["policy"]["auto_approve"] = False
        value["changes"] = {
            key: item
            for key, item in dict(value.get("changes", {})).items()
            if key in SAFE_PORTFOLIO_POLICY_FIELDS
        }
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StrategicPolicyRevision":
        source = dict(value or {})
        allowed = {item.name for item in cls.__dataclass_fields__.values()}
        item = cls(**{key: source[key] for key in allowed if key in source})
        item.revision_id = str(item.revision_id).strip()
        item.parent_revision_id = str(item.parent_revision_id).strip()
        item.status = str(item.status).upper().strip() or "PROPOSED"
        item.reason = str(item.reason).strip()
        item.evidence_count = max(0, int(item.evidence_count or 0))
        item.confidence = min(1.0, max(0.0, float(item.confidence or 0.0)))
        item.policy = dict(item.policy or {})
        item.policy["max_active_goals"] = 1
        item.policy["auto_approve"] = False
        item.changes = {
            key: value
            for key, value in dict(item.changes or {}).items()
            if key in SAFE_PORTFOLIO_POLICY_FIELDS
        }
        item.metrics = StrategicLearningMetrics.from_dict(item.metrics).to_dict()
        item.metadata = dict(item.metadata or {})
        return item

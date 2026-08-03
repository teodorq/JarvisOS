from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class StrategicPolicyValidationPolicy:
    enabled: bool = True
    validation_interval_seconds: float = 300.0
    observation_window: int = 500
    min_observations: int = 3
    top_k: int = 5
    min_utility_improvement: float = 0.0
    max_failure_exposure_increase: float = 0.0
    max_deferred_exposure_increase: float = 0.20
    min_top_k_overlap: float = 0.20
    max_changed_fields: int = 6
    max_history: int = 1000
    max_experiments: int = 200
    require_validation: bool = True
    auto_promote_validated: bool = True
    start_b60_with_supervisor: bool = True
    auto_approve: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["auto_approve"] = False
        return value

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any] | None,
    ) -> "StrategicPolicyValidationPolicy":
        source = dict(value or {})
        return cls(
            enabled=bool(source.get("enabled", True)),
            validation_interval_seconds=cls._bounded(
                source.get("validation_interval_seconds", 300.0), 60.0, 86400.0
            ),
            observation_window=int(cls._bounded(
                source.get("observation_window", 500), 10, 5000
            )),
            min_observations=int(cls._bounded(
                source.get("min_observations", 3), 1, 1000
            )),
            top_k=int(cls._bounded(source.get("top_k", 5), 1, 20)),
            min_utility_improvement=cls._bounded(
                source.get("min_utility_improvement", 0.0), -10.0, 50.0
            ),
            max_failure_exposure_increase=cls._bounded(
                source.get("max_failure_exposure_increase", 0.0), 0.0, 1.0
            ),
            max_deferred_exposure_increase=cls._bounded(
                source.get("max_deferred_exposure_increase", 0.20), 0.0, 1.0
            ),
            min_top_k_overlap=cls._bounded(
                source.get("min_top_k_overlap", 0.20), 0.0, 1.0
            ),
            max_changed_fields=int(cls._bounded(
                source.get("max_changed_fields", 6), 1, 10
            )),
            max_history=int(cls._bounded(
                source.get("max_history", 1000), 100, 5000
            )),
            max_experiments=int(cls._bounded(
                source.get("max_experiments", 200), 10, 1000
            )),
            require_validation=bool(source.get("require_validation", True)),
            auto_promote_validated=bool(
                source.get("auto_promote_validated", True)
            ),
            start_b60_with_supervisor=bool(
                source.get("start_b60_with_supervisor", True)
            ),
            auto_approve=False,
        )

    @staticmethod
    def _bounded(value: Any, minimum: float, maximum: float) -> float:
        return min(maximum, max(minimum, float(value or 0.0)))


@dataclass(slots=True)
class StrategicPolicyExperiment:
    revision_id: str
    baseline_revision_id: str
    candidate_policy: dict[str, Any]
    baseline_policy: dict[str, Any]
    experiment_id: str = field(
        default_factory=lambda: f"policy-experiment-{uuid4().hex}"
    )
    status: str = "CREATED"
    decision: str = "HOLD"
    reason: str = ""
    evidence_signature: str = ""
    evidence_count: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    checks: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    completed_at: str = ""
    promoted_at: str = ""
    rejected_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_policy"] = dict(value.get("candidate_policy", {}))
        value["candidate_policy"]["max_active_goals"] = 1
        value["candidate_policy"]["auto_approve"] = False
        value["baseline_policy"] = dict(value.get("baseline_policy", {}))
        value["baseline_policy"]["max_active_goals"] = 1
        value["baseline_policy"]["auto_approve"] = False
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StrategicPolicyExperiment":
        source = dict(value or {})
        allowed = {item.name for item in cls.__dataclass_fields__.values()}
        item = cls(**{key: source[key] for key in allowed if key in source})
        item.experiment_id = str(item.experiment_id).strip()
        item.revision_id = str(item.revision_id).strip()
        item.baseline_revision_id = str(item.baseline_revision_id).strip()
        item.status = str(item.status).upper().strip() or "CREATED"
        item.decision = str(item.decision).upper().strip() or "HOLD"
        item.reason = str(item.reason).strip()
        item.evidence_signature = str(item.evidence_signature).strip()
        item.evidence_count = max(0, int(item.evidence_count or 0))
        item.candidate_policy = dict(item.candidate_policy or {})
        item.candidate_policy["max_active_goals"] = 1
        item.candidate_policy["auto_approve"] = False
        item.baseline_policy = dict(item.baseline_policy or {})
        item.baseline_policy["max_active_goals"] = 1
        item.baseline_policy["auto_approve"] = False
        item.metrics = dict(item.metrics or {})
        item.checks = dict(item.checks or {})
        item.metadata = dict(item.metadata or {})
        return item

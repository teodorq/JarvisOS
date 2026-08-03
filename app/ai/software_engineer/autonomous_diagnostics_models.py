from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class AutonomousDiagnostic:
    job_id: str = ""
    autonomy_run_id: str = ""
    portfolio_id: str = ""
    director_run_id: str = ""
    source_status: str = "UNKNOWN"
    category: str = "UNKNOWN"
    severity: str = "WARNING"
    stage: str = "UNKNOWN"
    summary: str = ""
    root_cause: str = ""
    retryable: bool = False
    repairable: bool = False
    requires_approval: bool = False
    repair_type: str = "NONE"
    diagnostic_id: str = field(
        default_factory=lambda: f"diagnostic-{uuid4().hex}"
    )
    created_at: str = field(default_factory=utc_now)
    errors: list[str] = field(default_factory=list)
    traceback: str = ""
    stdout: str = ""
    stderr: str = ""
    files: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AutonomousDiagnostic":
        return cls(
            diagnostic_id=str(value.get("diagnostic_id", ""))
            or f"diagnostic-{uuid4().hex}",
            created_at=str(value.get("created_at", "")) or utc_now(),
            job_id=str(value.get("job_id", "")),
            autonomy_run_id=str(value.get("autonomy_run_id", "")),
            portfolio_id=str(value.get("portfolio_id", "")),
            director_run_id=str(value.get("director_run_id", "")),
            source_status=str(value.get("source_status", "UNKNOWN")),
            category=str(value.get("category", "UNKNOWN")),
            severity=str(value.get("severity", "WARNING")),
            stage=str(value.get("stage", "UNKNOWN")),
            summary=str(value.get("summary", "")),
            root_cause=str(value.get("root_cause", "")),
            retryable=bool(value.get("retryable", False)),
            repairable=bool(value.get("repairable", False)),
            requires_approval=bool(value.get("requires_approval", False)),
            repair_type=str(value.get("repair_type", "NONE")),
            errors=[str(item) for item in value.get("errors", [])][:50],
            traceback=str(value.get("traceback", "")),
            stdout=str(value.get("stdout", "")),
            stderr=str(value.get("stderr", "")),
            files=[str(item) for item in value.get("files", [])][:100],
            statuses=[str(item) for item in value.get("statuses", [])][:100],
            suggested_actions=[
                str(item) for item in value.get("suggested_actions", [])
            ][:20],
            evidence=dict(value.get("evidence", {}) or {}),
            metadata=dict(value.get("metadata", {}) or {}),
        )

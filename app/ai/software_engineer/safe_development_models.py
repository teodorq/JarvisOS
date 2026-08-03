from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, fields
from typing import Any


@dataclass(frozen=True, slots=True)
class SafeDevelopmentPolicy:
    """Bounded policy for approval-gated self-development."""

    max_changed_files: int = 1
    max_changed_lines: int = 40
    max_source_bytes: int = 900_000
    max_sessions: int = 20
    focused_test_limit: int = 12
    focused_test_timeout_seconds: int = 180
    live_test_timeout_seconds: int = 180
    allowed_prefixes: tuple[str, ...] = ("app/",)
    protected_fragments: tuple[str, ...] = (
        "/.git/",
        "/.venv/",
        "/AI_PLIKI/",
        "/archive/",
        "/data/",
        "/tests/",
        "/config/",
    )
    auto_approve: bool = False
    auto_deploy: bool = False
    auto_rollback: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SafeDevelopmentSession:
    """Persistent description of one isolated code-change proposal."""

    session_id: str
    status: str
    created_at: str
    updated_at: str
    target: str
    transform: str
    title: str
    rationale: str
    risk_score: float
    confidence: float
    changed_files: list[str] = field(default_factory=list)
    changed_lines: int = 0
    source_hash: str = ""
    proposed_hash: str = ""
    fingerprint: str = ""
    workspace_path: str = ""
    original_artifact: str = ""
    proposed_artifact: str = ""
    diff_artifact: str = ""
    backup_path: str = ""
    focused_tests: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    deployment: dict[str, Any] = field(default_factory=dict)
    rollback: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SafeDevelopmentSession":
        payload: dict[str, Any] = {}
        for item in fields(cls):
            if item.name in value:
                payload[item.name] = value[item.name]
            elif item.default is not MISSING:
                payload[item.name] = item.default
            elif item.default_factory is not MISSING:
                payload[item.name] = item.default_factory()
        for name in ("changed_files", "focused_tests", "errors", "warnings"):
            payload[name] = list(value.get(name, []) or [])
        for name in ("validation", "deployment", "rollback", "metadata"):
            payload[name] = dict(value.get(name, {}) or {})
        return cls(**payload)


TERMINAL_SESSION_STATES = {
    "DEPLOYED",
    "ROLLED_BACK",
    "DISCARDED",
    "FAILED",
    "STALE",
}

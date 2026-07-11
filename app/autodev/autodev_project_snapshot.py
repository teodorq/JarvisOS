from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AutoDevProjectSnapshot:
    created_at: str
    files_count: int
    python_files_count: int
    total_lines: int
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        files_count: int,
        python_files_count: int,
        total_lines: int,
        errors: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AutoDevProjectSnapshot":
        return cls(
            created_at=datetime.now().isoformat(),
            files_count=max(0, int(files_count)),
            python_files_count=max(0, int(python_files_count)),
            total_lines=max(0, int(total_lines)),
            errors=list(errors or []),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

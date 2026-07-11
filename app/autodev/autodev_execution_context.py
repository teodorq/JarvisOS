from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AutoDevExecutionContext:
    goal: str
    source: str = "AutoDevRuntime"
    dry_run: bool = True
    approved: bool = False
    writes_code: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

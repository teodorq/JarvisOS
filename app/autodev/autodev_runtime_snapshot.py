from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AutoDevRuntimeSnapshot:
    created_at: str
    queue: dict[str, Any]
    scheduler: dict[str, Any]
    monitor: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        queue: dict[str, Any],
        scheduler: dict[str, Any],
        monitor: dict[str, Any],
    ) -> "AutoDevRuntimeSnapshot":
        return cls(
            created_at=datetime.now().isoformat(),
            queue=dict(queue),
            scheduler=dict(scheduler),
            monitor=dict(monitor),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

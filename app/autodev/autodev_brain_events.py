from __future__ import annotations

from datetime import datetime
from typing import Any


class AutoDevBrainEvents:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        event = {
            "name": str(name).strip().upper(),
            "payload": dict(payload or {}),
            "created_at": datetime.now().isoformat(),
        }

        self.events.append(event)
        return dict(event)

    def last(self) -> dict[str, Any] | None:
        if not self.events:
            return None

        return dict(self.events[-1])

    def status(self) -> dict[str, Any]:
        return {
            "count": len(self.events),
            "last": self.last(),
        }

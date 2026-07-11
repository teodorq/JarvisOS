from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class BackgroundEvent:
    event_type: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "message": self.message,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


class BackgroundEventLog:

    def __init__(self, max_events: int = 500) -> None:
        self.max_events = max(1, int(max_events))
        self.events: list[BackgroundEvent] = []

    def add(
        self,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> BackgroundEvent:
        event = BackgroundEvent(
            event_type=str(event_type),
            message=str(message),
            metadata=dict(metadata or {}),
        )
        self.events.append(event)

        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        return event

    def last(self) -> BackgroundEvent | None:
        return self.events[-1] if self.events else None

    def summary(self) -> dict[str, Any]:
        return {
            "count": len(self.events),
            "last": self.last().to_dict() if self.last() else None,
        }

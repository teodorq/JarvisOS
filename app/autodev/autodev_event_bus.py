from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable


EventHandler = Callable[[dict[str, Any]], None]


class AutoDevEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self.history: list[dict[str, Any]] = []

    def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
    ) -> None:
        normalized = str(event_name).strip().upper()
        if not normalized:
            raise ValueError("Nazwa zdarzenia nie może być pusta.")

        if handler not in self._handlers[normalized]:
            self._handlers[normalized].append(handler)

    def publish(
        self,
        event_name: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(event_name).strip().upper()

        event = {
            "event": normalized,
            "payload": dict(payload or {}),
            "created_at": datetime.now().isoformat(),
        }

        self.history.append(event)

        for handler in list(self._handlers.get(normalized, [])):
            handler(dict(event))

        return dict(event)

    def status(self) -> dict[str, Any]:
        return {
            "events_count": len(self.history),
            "subscriptions": {
                name: len(handlers)
                for name, handlers in self._handlers.items()
            },
            "last_event": (
                dict(self.history[-1])
                if self.history
                else None
            ),
        }

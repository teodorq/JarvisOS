from __future__ import annotations

from collections import deque
from typing import Any


class AutoDevQueueService:
    def __init__(
        self,
        max_items: int = 100,
    ) -> None:
        self.max_items = max(1, int(max_items))
        self._queue: deque[dict[str, Any]] = deque()

    def enqueue(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        if len(self._queue) >= self.max_items:
            raise RuntimeError("Kolejka AutoDev jest pełna.")

        normalized = dict(item)
        self._queue.append(normalized)
        return dict(normalized)

    def dequeue(self) -> dict[str, Any] | None:
        if not self._queue:
            return None

        return dict(self._queue.popleft())

    def peek(self) -> dict[str, Any] | None:
        if not self._queue:
            return None

        return dict(self._queue[0])

    def clear(self) -> None:
        self._queue.clear()

    def status(self) -> dict[str, Any]:
        return {
            "count": len(self._queue),
            "max_items": self.max_items,
            "next": self.peek(),
        }

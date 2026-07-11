from __future__ import annotations

from collections import deque
from typing import Any


class AutoDevBrainQueue:
    def __init__(
        self,
        max_items: int = 100,
    ) -> None:

        self.max_items = max(
            1,
            int(max_items),
        )

        self._items: deque[
            dict[str, Any]
        ] = deque()

    def add(
        self,
        item: dict[str, Any],
    ) -> dict[str, Any]:

        if len(self._items) >= self.max_items:
            raise RuntimeError(
                "Kolejka Brain AutoDev jest pełna."
            )

        normalized = dict(item)
        self._items.append(normalized)

        return dict(normalized)

    def next(
        self,
    ) -> dict[str, Any] | None:

        if not self._items:
            return None

        return dict(
            self._items.popleft()
        )

    def status(self) -> dict[str, Any]:
        return {
            "count": len(self._items),
            "max_items": self.max_items,
            "next": (
                dict(self._items[0])
                if self._items
                else None
            ),
        }

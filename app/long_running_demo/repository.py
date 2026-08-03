from __future__ import annotations

"""Repozytorium danych dla funkcjonalności LongRunningDemo."""

from typing import Any


class LongRunningDemoRepository:
    """Proste repozytorium możliwe do zastąpienia adapterem trwałym."""

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def save(
        self,
        key: str,
        value: Any,
    ) -> None:
        normalized = str(
            key
        ).strip()

        if not normalized:
            raise ValueError(
                "Klucz repozytorium nie może być pusty."
            )

        self._items[normalized] = value

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        return self._items.get(
            str(key),
            default,
        )

    def snapshot(self) -> dict[str, Any]:
        return dict(
            self._items
        )

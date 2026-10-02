"""Consistent non-queued busy feedback for the compact client UI."""

from __future__ import annotations

from typing import Any


def publish_client_busy(window: Any, *, confirmed: bool = False) -> None:
    detail = (
        "Zatwierdzone działanie nie zostało dodane do opóźnionej kolejki."
        if confirmed
        else "Spróbuj ponownie za chwilę; nie dodałem tego polecenia do "
        "opóźnionej kolejki."
    )
    window._publish_client_event(
        state="warning",
        message=f"Kończę poprzednie zadanie. {detail}",
        progress=60 if confirmed else 18,
    )


__all__ = ["publish_client_busy"]

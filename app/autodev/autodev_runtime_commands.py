from __future__ import annotations

from typing import Any

from app.autodev.autodev_runtime_service import (
    AutoDevRuntimeService,
)


class AutoDevRuntimeCommands:
    """
    Polecenia uruchomieniowe dla AutoDev Intelligence.

    Obsługiwane komendy:
    - autodev runtime status
    - autodev runtime analyze
    - autodev runtime preview
    - analiza runtime autodev
    - podgląd runtime autodev
    """

    COMMANDS = (
        "autodev runtime status",
        "status autodev runtime",
        "autodev runtime analyze",
        "autodev runtime analyse",
        "analiza runtime autodev",
        "analizuj runtime autodev",
        "autodev runtime preview",
        "podgląd runtime autodev",
        "podglad runtime autodev",
    )

    def __init__(
        self,
        service: AutoDevRuntimeService,
    ) -> None:

        self.service = service

    def can_handle(
        self,
        command: str,
    ) -> bool:

        normalized = str(
            command
        ).strip().casefold()

        return any(
            phrase in normalized
            for phrase in self.COMMANDS
        )

    def handle(
        self,
        command: str,
    ) -> dict[str, Any]:

        normalized = str(
            command
        ).strip().casefold()

        if "status" in normalized:
            return self.service.status()

        if (
            "preview" in normalized
            or "podgląd" in normalized
            or "podglad" in normalized
        ):
            return self.service.preview()

        return self.service.analyze()

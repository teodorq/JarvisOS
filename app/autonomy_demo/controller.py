from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności AutonomyDemo."""

from typing import Any

from .models import (
    AutonomyDemoRequest,
    AutonomyDemoResult,
)
from .service import AutonomyDemoService


class AutonomyDemoController:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "autonomy demo",
        "autonomydemo",
    )

    def __init__(
        self,
        service: AutonomyDemoService | None = None,
    ) -> None:
        self.service = (
            service
            or AutonomyDemoService()
        )

    @classmethod
    def can_handle(
        cls,
        command: str,
    ) -> bool:
        normalized = " ".join(
            str(command).casefold().split()
        )
        return any(
            phrase in normalized
            for phrase in cls.COMMAND_PHRASES
        )

    def handle(
        self,
        command: str,
        payload: dict[str, Any] | None = None,
    ) -> AutonomyDemoResult:
        if not self.can_handle(
            command
        ):
            return AutonomyDemoResult(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            AutonomyDemoRequest(
                payload=dict(
                    payload or {}
                )
            )
        )

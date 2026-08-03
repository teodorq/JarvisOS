from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności LongRunningDemo."""

from typing import Any

from .models import (
    LongRunningDemoRequest,
    LongRunningDemoResult,
)
from .service import LongRunningDemoService


class LongRunningDemoController:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "long running demo",
        "longrunningdemo",
    )

    def __init__(
        self,
        service: LongRunningDemoService | None = None,
    ) -> None:
        self.service = (
            service
            or LongRunningDemoService()
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
    ) -> LongRunningDemoResult:
        if not self.can_handle(
            command
        ):
            return LongRunningDemoResult(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            LongRunningDemoRequest(
                payload=dict(
                    payload or {}
                )
            )
        )

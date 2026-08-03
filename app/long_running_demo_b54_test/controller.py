from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności LongRunningDemoB54Test."""

from typing import Any

from .models import (
    LongRunningDemoB54TestRequest,
    LongRunningDemoB54TestResult,
)
from .service import LongRunningDemoB54TestService


class LongRunningDemoB54TestController:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "long running demo b54 test",
        "longrunningdemob54test",
    )

    def __init__(
        self,
        service: LongRunningDemoB54TestService | None = None,
    ) -> None:
        self.service = (
            service
            or LongRunningDemoB54TestService()
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
    ) -> LongRunningDemoB54TestResult:
        if not self.can_handle(
            command
        ):
            return LongRunningDemoB54TestResult(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            LongRunningDemoB54TestRequest(
                payload=dict(
                    payload or {}
                )
            )
        )

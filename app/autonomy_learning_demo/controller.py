from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności AutonomyLearningDemo."""

from typing import Any

from .models import (
    AutonomyLearningDemoRequest,
    AutonomyLearningDemoResult,
)
from .service import AutonomyLearningDemoService


class AutonomyLearningDemoController:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "autonomy learning demo",
        "autonomylearningdemo",
    )

    def __init__(
        self,
        service: AutonomyLearningDemoService | None = None,
    ) -> None:
        self.service = (
            service
            or AutonomyLearningDemoService()
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
    ) -> AutonomyLearningDemoResult:
        if not self.can_handle(
            command
        ):
            return AutonomyLearningDemoResult(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            AutonomyLearningDemoRequest(
                payload=dict(
                    payload or {}
                )
            )
        )

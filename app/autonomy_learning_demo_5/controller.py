from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności AutonomyLearningDemo5."""

from typing import Any

from .models import (
    AutonomyLearningDemo5Request,
    AutonomyLearningDemo5Result,
)
from .service import AutonomyLearningDemo5Service


class AutonomyLearningDemo5Controller:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "autonomy learning demo5",
        "autonomylearningdemo5",
    )

    def __init__(
        self,
        service: AutonomyLearningDemo5Service | None = None,
    ) -> None:
        self.service = (
            service
            or AutonomyLearningDemo5Service()
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
    ) -> AutonomyLearningDemo5Result:
        if not self.can_handle(
            command
        ):
            return AutonomyLearningDemo5Result(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            AutonomyLearningDemo5Request(
                payload=dict(
                    payload or {}
                )
            )
        )

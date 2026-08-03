from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności AutonomyLearningDemo2."""

from typing import Any

from .models import (
    AutonomyLearningDemo2Request,
    AutonomyLearningDemo2Result,
)
from .service import AutonomyLearningDemo2Service


class AutonomyLearningDemo2Controller:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "autonomy learning demo2",
        "autonomylearningdemo2",
    )

    def __init__(
        self,
        service: AutonomyLearningDemo2Service | None = None,
    ) -> None:
        self.service = (
            service
            or AutonomyLearningDemo2Service()
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
    ) -> AutonomyLearningDemo2Result:
        if not self.can_handle(
            command
        ):
            return AutonomyLearningDemo2Result(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            AutonomyLearningDemo2Request(
                payload=dict(
                    payload or {}
                )
            )
        )

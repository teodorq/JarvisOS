from __future__ import annotations

"""Kontroler wejścia dla funkcjonalności AutonomyLearningDemo4."""

from typing import Any

from .models import (
    AutonomyLearningDemo4Request,
    AutonomyLearningDemo4Result,
)
from .service import AutonomyLearningDemo4Service


class AutonomyLearningDemo4Controller:
    """Waliduje polecenie i deleguje logikę do serwisu."""

    COMMAND_PHRASES = (
        "autonomy learning demo4",
        "autonomylearningdemo4",
    )

    def __init__(
        self,
        service: AutonomyLearningDemo4Service | None = None,
    ) -> None:
        self.service = (
            service
            or AutonomyLearningDemo4Service()
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
    ) -> AutonomyLearningDemo4Result:
        if not self.can_handle(
            command
        ):
            return AutonomyLearningDemo4Result(
                success=False,
                status="UNSUPPORTED_COMMAND",
                errors=[
                    "Polecenie nie pasuje do kontrolera.",
                ],
            )

        return self.service.execute(
            AutonomyLearningDemo4Request(
                payload=dict(
                    payload or {}
                )
            )
        )

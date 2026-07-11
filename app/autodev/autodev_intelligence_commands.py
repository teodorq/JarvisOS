from __future__ import annotations

from typing import Any

from app.autodev.autodev_intelligence_orchestrator import (
    AutoDevIntelligenceOrchestrator,
)


class AutoDevIntelligenceCommands:
    """
    Obsługuje proste polecenia tekstowe dla Intelligence V2.
    """

    COMMANDS = (
        "autodev intelligence status",
        "status autodev intelligence",
        "autodev intelligence analyze",
        "analizuj autodev intelligence",
        "autodev intelligence preview",
        "podgląd autodev intelligence",
        "podglad autodev intelligence",
    )

    def __init__(
        self,
        orchestrator: AutoDevIntelligenceOrchestrator,
    ) -> None:

        self.orchestrator = orchestrator

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
            return {
                "success": True,
                "status": "AUTODEV_INTELLIGENCE_STATUS",
                "data": self.orchestrator.status(),
            }

        if (
            "preview" in normalized
            or "podgląd" in normalized
            or "podglad" in normalized
        ):
            return self.orchestrator.preview_selected()

        return self.orchestrator.analyze()

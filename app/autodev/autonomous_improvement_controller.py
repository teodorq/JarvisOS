from __future__ import annotations

from typing import Any

from app.autodev.autonomous_improvement_service import (
    AutonomousImprovementService,
)


class AutonomousImprovementController:
    """
    Kontroler poleceń autonomicznego ulepszania.

    Obsługiwane operacje:
    - podgląd bez zapisu,
    - wykonanie zatwierdzonego cyklu,
    - status.
    """

    COMMANDS = (
        "podgląd autonomicznego ulepszenia",
        "podglad autonomicznego ulepszenia",
        "preview autonomous improvement",
        "uruchom autonomiczne ulepszenie",
        "wykonaj autonomiczne ulepszenie",
        "zatwierdź autonomiczne ulepszenie",
        "zatwierdz autonomiczne ulepszenie",
        "status autonomicznego ulepszania",
        "status autonomous improvement",
    )

    def __init__(
        self,
        service: AutonomousImprovementService,
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
            return {
                "success": True,
                "status": (
                    "AUTONOMOUS_IMPROVEMENT_STATUS"
                ),
                "service": self.service.status(),
            }

        if (
            "zatwierdź" in normalized
            or "zatwierdz" in normalized
            or "wykonaj" in normalized
        ):
            result = (
                self.service.execute_approved()
            )

            return {
                "controller_status": (
                    "APPROVED_CYCLE_FINISHED"
                ),
                **result,
            }

        result = self.service.preview()

        return {
            "controller_status": (
                "PREVIEW_CYCLE_FINISHED"
            ),
            **result,
        }

from __future__ import annotations

from typing import Any

from app.autodev.background_service import BackgroundAutonomyService


class BackgroundCommands:

    PREFIXES = (
        "background autodev ",
        "autodev background ",
        "auto rozwój w tle ",
        "auto rozwoj w tle ",
    )

    def __init__(
        self,
        service: BackgroundAutonomyService | None = None,
    ) -> None:
        self.service = service or BackgroundAutonomyService()

    def can_handle(self, command: str) -> bool:
        normalized = str(command).strip().casefold()
        return normalized.startswith(self.PREFIXES)

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(command).strip().casefold()

        if " start" in normalized or " uruchom" in normalized:
            return self.service.start()

        if " stop" in normalized or " zatrzymaj" in normalized:
            return self.service.stop()

        if " status" in normalized or " stan" in normalized:
            return self.service.status()

        if " tick" in normalized or " sprawdź" in normalized or " sprawdz" in normalized:
            return self.service.tick()

        return {
            "success": False,
            "status": "UNKNOWN_COMMAND",
            "command": command,
        }

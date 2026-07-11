from __future__ import annotations

from typing import Any

from app.autodev.autonomous_api import AutonomousAPI


class AutonomousCommands:
    """
    Text command adapter used by Brain and UI layers.
    """

    PREFIXES = (
        "autonomous ",
        "autonomia ",
        "autonomiczny tryb ",
    )

    def __init__(
        self,
        api: AutonomousAPI | None = None,
    ) -> None:
        self.api = api or AutonomousAPI()

    def can_handle(self, command: str) -> bool:
        normalized = str(command).strip().casefold()
        return normalized.startswith(self.PREFIXES)

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(command).strip().casefold()

        if not normalized:
            return {
                "success": False,
                "status": "EMPTY_COMMAND",
            }

        if any(
            token in normalized
            for token in (" start", " uruchom")
        ):
            max_cycles = self._extract_cycle_limit(normalized)

            return self.api.start(
                max_cycles=max_cycles,
                background=True,
                context=context,
            )

        if any(
            token in normalized
            for token in (" stop", " zatrzymaj")
        ):
            return self.api.stop()

        if " status" in normalized or " stan" in normalized:
            return self.api.status()

        if " stats" in normalized or " statystyki" in normalized:
            return self.api.stats()

        if " learning" in normalized or " nauka" in normalized:
            return self.api.learning()

        return {
            "success": False,
            "status": "UNKNOWN_COMMAND",
            "command": command,
        }

    def _extract_cycle_limit(
        self,
        command: str,
    ) -> int | None:
        parts = command.replace("=", " ").split()

        for index, part in enumerate(parts):
            if part in {"cycles", "cykle", "cycle", "cykl"}:
                if index + 1 < len(parts):
                    try:
                        value = int(parts[index + 1])
                    except ValueError:
                        return None

                    return value if value > 0 else None

        return None

from __future__ import annotations

from typing import Any

from app.autodev.autodev_autonomy_service import (
    AutoDevAutonomyService,
)
from app.autodev.autodev_pipeline import AutoDevPipeline


class AutoDevAutonomyController:

    COMMANDS = (
        "uruchom autonomię autodev",
        "uruchom autonomie autodev",
        "autonomia autodev",
        "wygeneruj zadania rozwojowe",
        "utwórz zadania rozwojowe",
        "utworz zadania rozwojowe",
        "status autonomii autodev",
    )

    def __init__(
        self,
        pipeline: AutoDevPipeline,
    ) -> None:

        self.service = AutoDevAutonomyService(
            pipeline
        )

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
                "status": "AUTONOMY_STATUS",
                **self.service.status(),
            }

        result = self.service.run_cycle()

        return {
            "status": "AUTONOMY_CYCLE_COMPLETED",
            **result,
        }
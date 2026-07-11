from __future__ import annotations

from typing import Any

from app.autodev.autodev_autonomy_service import (
    AutoDevAutonomyService,
)
from app.autodev.autodev_background_loop import (
    AutoDevBackgroundLoop,
)


class AutoDevBackgroundController:

    COMMANDS = (
        "uruchom pętlę autodev",
        "uruchom petle autodev",
        "start autodev background",
        "zatrzymaj pętlę autodev",
        "zatrzymaj petle autodev",
        "stop autodev background",
        "status pętli autodev",
        "status petli autodev",
        "status autodev background",
        "wykonaj cykl autodev",
    )

    def __init__(
        self,
        service: AutoDevAutonomyService,
        interval_seconds: float = 60.0,
    ) -> None:

        self.loop = AutoDevBackgroundLoop(
            service=service,
            interval_seconds=interval_seconds,
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

        if (
            "status" in normalized
        ):
            return {
                "success": True,
                "status": "BACKGROUND_STATUS",
                **self.loop.status(),
            }

        if (
            "zatrzymaj" in normalized
            or "stop" in normalized
        ):
            stopped = self.loop.stop(
                wait=False
            )

            return {
                "success": True,
                "status": (
                    "BACKGROUND_STOPPED"
                    if stopped
                    else "BACKGROUND_ALREADY_STOPPED"
                ),
                **self.loop.status(),
            }

        if (
            "wykonaj cykl" in normalized
        ):
            result = self.loop.run_once()

            return {
                "success": bool(
                    result.get(
                        "success",
                        False,
                    )
                ),
                "status": "BACKGROUND_CYCLE_COMPLETED",
                "result": result,
                **self.loop.status(),
            }

        started = self.loop.start()

        return {
            "success": True,
            "status": (
                "BACKGROUND_STARTED"
                if started
                else "BACKGROUND_ALREADY_RUNNING"
            ),
            **self.loop.status(),
        }

    def shutdown(
        self,
    ) -> None:

        self.loop.stop(
            wait=True
        )

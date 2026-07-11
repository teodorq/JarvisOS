from __future__ import annotations

from typing import Any

from app.autodev.autodev_autonomy_coordinator import (
    AutoDevAutonomyCoordinator,
)
from app.autodev.autodev_brain_bridge import (
    AutoDevBrainBridge,
)
from app.autodev.autodev_brain_scheduler import (
    AutoDevBrainScheduler,
)
from app.autodev.autodev_cycle_coordinator import (
    AutoDevCycleCoordinator,
)


class AutoDevBrainIntegration:
    COMMANDS = (
        "jarvis autodev autonomy status",
        "jarvis autodev autonomy run",
    )

    def __init__(
        self,
        bridge: AutoDevBrainBridge | None = None,
    ) -> None:

        self.bridge = (
            bridge
            or AutoDevBrainBridge()
        )

        self.cycle_coordinator = (
            AutoDevCycleCoordinator(
                bridge=self.bridge
            )
        )

        self.scheduler = AutoDevBrainScheduler(
            coordinator=self.cycle_coordinator
        )

        self.autonomy = (
            AutoDevAutonomyCoordinator(
                brain_scheduler=self.scheduler
            )
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
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized = str(
            command
        ).strip().casefold()

        context = dict(
            context or {}
        )

        if "status" in normalized:
            return {
                "success": True,
                "status": "AUTODEV_AUTONOMY_STATUS",
                "data": self.autonomy.status(),
            }

        candidates = context.get(
            "candidates"
        )

        if not isinstance(
            candidates,
            list,
        ):
            goal = str(
                context.get(
                    "goal",
                    "",
                )
            ).strip()

            candidates = (
                [
                    {
                        "goal": goal,
                        "priority_score": 10.0,
                        "risk_score": 0.0,
                    }
                ]
                if goal
                else []
            )

        return self.autonomy.run(
            candidates
        )

from __future__ import annotations

from typing import Any

from app.autodev.autodev_runtime_controller import (
    AutoDevRuntimeController,
)
from app.autodev.autodev_runtime_facade import (
    AutoDevRuntimeFacade,
)


class AutoDevBrainBridge:
    COMMANDS = (
        "jarvis autodev status",
        "jarvis autodev analyze",
        "jarvis autodev preview",
        "jarvis autodev run next",
        "jarvis autodev queue",
        "jarvis autodev snapshot",
    )

    def __init__(
        self,
        controller: AutoDevRuntimeController | None = None,
    ) -> None:

        self.controller = (
            controller
            or AutoDevRuntimeController()
        )

        self.facade = AutoDevRuntimeFacade(
            controller=self.controller
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
                "status": "BRAIN_BRIDGE_STATUS",
                "runtime": self.facade.status(),
            }

        if "snapshot" in normalized:
            return {
                "success": True,
                "status": "SNAPSHOT_READY",
                "snapshot": self.facade.snapshot(),
            }

        if "run next" in normalized:
            return self.facade.run_next()

        if "preview" in normalized:
            return self.facade.preview()

        if "analyze" in normalized:
            return self.facade.analyze()

        prefix = "jarvis autodev queue"

        goal = str(
            context.get(
                "goal",
                "",
            )
        ).strip()

        if not goal:
            position = normalized.find(
                prefix
            )

            goal = command[
                position + len(prefix):
            ].strip()

        return self.facade.queue_task(
            {
                "title": goal,
                "goal": goal,
                "metadata": {
                    "source": "Brain",
                    **dict(
                        context.get(
                            "metadata"
                        )
                        or {}
                    ),
                },
            }
        )

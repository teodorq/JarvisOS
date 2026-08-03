from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from typing import Any

from app.autodev.autodev_cycle_executor import (
    AutoDevCycleExecutor,
)
from app.autodev.autodev_event_bus import AutoDevEventBus
from app.autodev.autodev_queue_service import (
    AutoDevQueueService,
)
from app.autodev.autodev_runtime_monitor import (
    AutoDevRuntimeMonitor,
)
from app.autodev.autodev_runtime_scheduler import (
    AutoDevRuntimeScheduler,
)
from app.autodev.autodev_runtime_service import (
    AutoDevRuntimeService,
)


class AutoDevRuntimeController:
    COMMANDS = (
        "autodev runtime status",
        "autodev runtime queue",
        "autodev runtime run next",
        "autodev runtime preview",
        "autodev runtime analyze",
    )

    def __init__(
        self,
        project_root: str = default_project_root(),
        runtime_service: AutoDevRuntimeService | None = None,
    ) -> None:
        self.runtime_service = (
            runtime_service
            or AutoDevRuntimeService(
                project_root=project_root
            )
        )

        self.event_bus = AutoDevEventBus()
        self.queue_service = AutoDevQueueService()
        self.cycle_executor = AutoDevCycleExecutor(
            runtime_service=self.runtime_service,
            event_bus=self.event_bus,
        )
        self.scheduler = AutoDevRuntimeScheduler(
            queue_service=self.queue_service,
            cycle_executor=self.cycle_executor,
        )
        self.monitor = AutoDevRuntimeMonitor(
            queue_service=self.queue_service,
            cycle_executor=self.cycle_executor,
        )

    def can_handle(
        self,
        command: str,
    ) -> bool:
        normalized = str(command).strip().casefold()

        return any(
            phrase in normalized
            for phrase in self.COMMANDS
        )

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(command).strip().casefold()
        context = dict(context or {})

        if "status" in normalized:
            return self.monitor.status()

        if "run next" in normalized:
            return self.scheduler.run_next()

        if "queue" in normalized:
            goal = str(
                context.get(
                    "goal",
                    "",
                )
            ).strip()

            if not goal:
                prefix = "autodev runtime queue"
                goal = command[
                    command.casefold().find(prefix)
                    + len(prefix):
                ].strip()

            return self.scheduler.schedule(
                goal,
                metadata={
                    "source": "AutoDevRuntimeController",
                    **dict(
                        context.get("metadata") or {}
                    ),
                },
            )

        if "preview" in normalized:
            return self.runtime_service.preview()

        return self.runtime_service.analyze()

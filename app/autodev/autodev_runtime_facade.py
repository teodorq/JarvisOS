from __future__ import annotations

from typing import Any

from app.autodev.autodev_runtime_controller import (
    AutoDevRuntimeController,
)
from app.autodev.autodev_runtime_snapshot import (
    AutoDevRuntimeSnapshot,
)
from app.autodev.autodev_task_dispatcher import (
    AutoDevTaskDispatcher,
)


class AutoDevRuntimeFacade:
    def __init__(
        self,
        controller: AutoDevRuntimeController,
    ) -> None:
        self.controller = controller
        self.dispatcher = AutoDevTaskDispatcher(
            scheduler=self.controller.scheduler
        )
        self.last_snapshot: dict[str, Any] | None = None

    def queue_task(
        self,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        return self.dispatcher.dispatch(
            task
        )

    def run_next(
        self,
    ) -> dict[str, Any]:
        return self.controller.scheduler.run_next()

    def analyze(
        self,
    ) -> dict[str, Any]:
        return self.controller.runtime_service.analyze()

    def preview(
        self,
    ) -> dict[str, Any]:
        return self.controller.runtime_service.preview()

    def snapshot(
        self,
    ) -> dict[str, Any]:
        snapshot = AutoDevRuntimeSnapshot.create(
            queue=self.controller.queue_service.status(),
            scheduler=self.controller.scheduler.status(),
            monitor=self.controller.monitor.status(),
        )

        result = snapshot.to_dict()
        self.last_snapshot = dict(result)
        return result

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "controller": self.controller.monitor.status(),
            "last_snapshot": self.last_snapshot,
            "last_dispatch": self.dispatcher.last_result,
        }

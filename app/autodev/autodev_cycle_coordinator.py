from __future__ import annotations

from typing import Any

from app.autodev.autodev_brain_events import (
    AutoDevBrainEvents,
)
from app.autodev.autodev_runtime_statistics import (
    AutoDevRuntimeStatistics,
)


class AutoDevCycleCoordinator:
    def __init__(
        self,
        bridge: Any,
        events: AutoDevBrainEvents | None = None,
        statistics: AutoDevRuntimeStatistics | None = None,
    ) -> None:

        self.bridge = bridge
        self.events = (
            events
            or AutoDevBrainEvents()
        )
        self.statistics = (
            statistics
            or AutoDevRuntimeStatistics()
        )
        self.last_result: dict[str, Any] | None = None

    def run_goal(
        self,
        goal: str,
    ) -> dict[str, Any]:

        normalized_goal = str(
            goal
        ).strip()

        if not normalized_goal:
            return {
                "success": False,
                "status": "EMPTY_GOAL",
            }

        self.statistics.started()

        self.events.emit(
            "BRAIN_AUTODEV_CYCLE_STARTED",
            {
                "goal": normalized_goal
            },
        )

        try:
            queued = self.bridge.handle(
                (
                    "jarvis autodev queue "
                    + normalized_goal
                )
            )

            if not queued.get(
                "success",
                False,
            ):
                result = dict(queued)
            else:
                result = self.bridge.handle(
                    "jarvis autodev run next"
                )

        except Exception as error:
            result = {
                "success": False,
                "status": "FAILED",
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
            }

        self.statistics.finished(
            bool(
                result.get(
                    "success",
                    False,
                )
            ),
            str(
                result.get(
                    "status",
                    "UNKNOWN",
                )
            ),
        )

        self.events.emit(
            "BRAIN_AUTODEV_CYCLE_FINISHED",
            result,
        )

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
            "events": self.events.status(),
            "statistics": self.statistics.status(),
        }

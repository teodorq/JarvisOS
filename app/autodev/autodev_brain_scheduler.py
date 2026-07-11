from __future__ import annotations

from typing import Any

from app.autodev.autodev_brain_queue import (
    AutoDevBrainQueue,
)
from app.autodev.autodev_cycle_coordinator import (
    AutoDevCycleCoordinator,
)
from app.autodev.autodev_goal_selector import (
    AutoDevGoalSelector,
)


class AutoDevBrainScheduler:
    def __init__(
        self,
        coordinator: AutoDevCycleCoordinator,
        queue: AutoDevBrainQueue | None = None,
        selector: AutoDevGoalSelector | None = None,
    ) -> None:

        self.coordinator = coordinator
        self.queue = (
            queue
            or AutoDevBrainQueue()
        )
        self.selector = (
            selector
            or AutoDevGoalSelector()
        )
        self.last_result: dict[str, Any] | None = None

    def schedule(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:

        selection = self.selector.select(
            candidates
        )

        selected = selection.get(
            "selected"
        )

        if selected is None:
            return {
                "success": True,
                "status": "NO_GOALS",
                "selected": None,
            }

        self.queue.add(
            selected
        )

        return {
            "success": True,
            "status": "GOAL_QUEUED",
            "selected": selected,
            "queue": self.queue.status(),
        }

    def run_next(self) -> dict[str, Any]:
        item = self.queue.next()

        if item is None:
            result = {
                "success": True,
                "status": "NO_GOALS",
            }
            self.last_result = result
            return result

        goal = str(
            item.get(
                "goal",
                item.get(
                    "title",
                    "",
                ),
            )
        ).strip()

        result = self.coordinator.run_goal(
            goal
        )

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "queue": self.queue.status(),
            "coordinator": self.coordinator.status(),
            "last_result": self.last_result,
        }

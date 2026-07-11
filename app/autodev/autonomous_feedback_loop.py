from __future__ import annotations

from typing import Any

from app.autodev.autonomous_lifecycle import AutonomousLifecycle
from app.autodev.followup_task_generator import (
    FollowupTaskGenerator,
)
from app.autodev.learning_bridge import LearningBridge


class AutonomousFeedbackLoop:
    """
    Closed loop:
    select task -> execute -> learn -> create follow-up tasks.
    """

    def __init__(
        self,
        *,
        lifecycle: AutonomousLifecycle,
        controller: Any,
        learning: LearningBridge | None = None,
        generator: FollowupTaskGenerator | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.controller = controller
        self.learning = learning or LearningBridge()
        self.generator = (
            generator or FollowupTaskGenerator()
        )
        self.history: list[dict[str, Any]] = []

    def run_cycle(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        execution = self.lifecycle.run_next(
            context=context
        )

        learning = self.learning.record(
            execution
        )

        generated = self.generator.generate(
            execution
        )

        queued: list[dict[str, Any]] = []
        queue_errors: list[str] = []

        for task in generated:
            try:
                queued_task = self._queue_task(
                    task
                )
                queued.append(
                    queued_task
                )
            except Exception as error:
                queue_errors.append(
                    f"{type(error).__name__}: {error}"
                )

        result = {
            "success": (
                bool(
                    execution.get(
                        "success",
                        False,
                    )
                )
                and not queue_errors
            ),
            "status": "CYCLE_COMPLETED",
            "execution": execution,
            "learning": learning,
            "generated_tasks": generated,
            "queued_tasks": queued,
            "queue_errors": queue_errors,
        }

        self.history.append(
            result
        )

        return result

    def run(
        self,
        *,
        max_cycles: int = 5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if max_cycles < 1:
            raise ValueError(
                "max_cycles musi być większe od 0."
            )

        results: list[dict[str, Any]] = []
        stop_reason = "MAX_CYCLES_REACHED"

        for _ in range(max_cycles):
            cycle = self.run_cycle(
                context=context
            )
            results.append(
                cycle
            )

            execution = cycle.get(
                "execution",
                {},
            )

            if (
                isinstance(
                    execution,
                    dict,
                )
                and execution.get(
                    "status"
                )
                == "NO_TASKS"
            ):
                stop_reason = "NO_TASKS"
                break

            if not cycle.get(
                "success",
                False,
            ):
                stop_reason = "FAILURE"
                break

        return {
            "success": stop_reason != "FAILURE",
            "status": "STOPPED",
            "stop_reason": stop_reason,
            "cycles_run": len(results),
            "results": results,
            "learning": self.learning.summary(),
        }

    def status(self) -> dict[str, Any]:
        return {
            "history_count": len(
                self.history
            ),
            "learning": self.learning.summary(),
        }

    def _queue_task(
        self,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        goal = str(
            task.get(
                "goal",
                "",
            )
        ).strip()

        if not goal:
            raise ValueError(
                "Wygenerowane zadanie nie posiada celu."
            )

        context = {
            "target": task.get(
                "target",
                "",
            ),
            "priority": task.get(
                "priority",
                "NORMAL",
            ),
            "tags": task.get(
                "tags",
                [
                    "autonomous-dev",
                    "followup",
                ],
            ),
            "metadata": {
                "source": "AutonomousFeedbackLoop",
                "generated_followup": True,
            },
        }

        queue_goal = getattr(
            self.controller,
            "queue_goal",
            None,
        )

        if callable(
            queue_goal
        ):
            return queue_goal(
                goal=goal,
                source="AutonomousFeedbackLoop",
                context=context,
            )

        submit_goal = getattr(
            self.controller,
            "submit_goal",
            None,
        )

        if callable(
            submit_goal
        ):
            return submit_goal(
                goal=goal,
                source="AutonomousFeedbackLoop",
                context=context,
            )

        raise AttributeError(
            "Controller nie obsługuje queue_goal ani submit_goal."
        )

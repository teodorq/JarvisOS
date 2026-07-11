from __future__ import annotations

from typing import Any

from app.autodev.autodev_cycle import AutoDevCycle
from app.autodev.autodev_pipeline import AutoDevPipeline
from app.autodev.continuous_improvement_coordinator import (
    ContinuousImprovementCoordinator,
)
from app.autodev.project_health_cycle import (
    ProjectHealthCycle,
)


class AutoDevAutonomyService:

    def __init__(
        self,
        pipeline: AutoDevPipeline,
    ) -> None:

        self.pipeline = pipeline

        self.development_cycle = AutoDevCycle(
            pipeline
        )

        self.health_cycle = ProjectHealthCycle(
            pipeline
        )

        self.improvement_coordinator = (
            ContinuousImprovementCoordinator(
                pipeline
            )
        )

        self.last_result: dict[str, Any] | None = None

    def run_cycle(
        self,
    ) -> dict[str, Any]:

        improvement_result = (
            self.improvement_coordinator
            .process_completed_tasks()
        )

        health_result = self.health_cycle.run()

        development_result = (
            self.development_cycle.run()
        )

        tasks_created = (
            int(
                health_result.get(
                    "tasks_created",
                    0,
                )
            )
            + int(
                development_result.get(
                    "tasks_created",
                    0,
                )
            )
        )

        pipeline_started = False

        if tasks_created > 0:
            pipeline_started = bool(
                self.pipeline.start()
            )

        errors = list(
            health_result.get(
                "errors",
                [],
            )
        )

        errors.extend(
            development_result.get(
                "errors",
                [],
            )
        )

        result = {
            "success": not errors,
            "tasks_created": tasks_created,
            "pipeline_started": pipeline_started,
            "improvement": improvement_result,
            "health": health_result,
            "development": development_result,
            "errors": errors,
        }

        self.last_result = dict(
            result
        )

        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "ready": True,
            "pipeline_running": (
                self.pipeline.is_running()
            ),
            "last_result": self.last_result,
            "health": self.health_cycle.status(),
            "improvement": (
                self.improvement_coordinator.status()
            ),
        }

    def reset(
        self,
    ) -> None:

        self.last_result = None

        self.improvement_coordinator.reset()
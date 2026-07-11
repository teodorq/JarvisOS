from __future__ import annotations

from typing import Any

from app.autodev.autodev_pipeline import (
    AutoDevPipeline,
)
from app.autodev.health_task_seeder import (
    HealthTaskSeeder,
)
from app.autodev.project_health_monitor import (
    ProjectHealthMonitor,
)


class ProjectHealthCycle:

    def __init__(
        self,
        pipeline: AutoDevPipeline,
    ) -> None:

        self.pipeline = pipeline
        self.monitor = ProjectHealthMonitor()

        self.seeder = HealthTaskSeeder(
            pipeline=self.pipeline
        )

        self.last_result: dict[str, Any] | None = None

    def run(
        self,
    ) -> dict[str, Any]:

        health_report = self.monitor.analyze()

        seed_result = self.seeder.seed()

        created_count = int(
            seed_result.get(
                "created_count",
                0,
            )
        )

        pipeline_started = False

        if created_count > 0:
            pipeline_started = bool(
                self.pipeline.start()
            )

        result = {
            "success": bool(
                seed_result.get(
                    "success",
                    False,
                )
            ),
            "healthy": bool(
                health_report.get(
                    "healthy",
                    False,
                )
            ),
            "issues_count": len(
                health_report.get(
                    "issues",
                    [],
                )
            ),
            "suggestions_count": len(
                health_report.get(
                    "suggestions",
                    [],
                )
            ),
            "tasks_created": created_count,
            "pipeline_started": pipeline_started,
            "errors": list(
                seed_result.get(
                    "errors",
                    [],
                )
            ),
            "health_report": health_report,
            "created_tasks": list(
                seed_result.get(
                    "created_tasks",
                    [],
                )
            ),
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
        }
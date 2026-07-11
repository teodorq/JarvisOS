from __future__ import annotations

from typing import Any

from app.autodev.project_health_monitor import (
    ProjectHealthMonitor,
)


class HealthTaskGenerator:

    def __init__(
        self,
        monitor: ProjectHealthMonitor | None = None,
    ) -> None:

        self.monitor = (
            monitor
            if monitor is not None
            else ProjectHealthMonitor()
        )

        self.last_tasks: list[
            dict[str, Any]
        ] = []

    def generate(
        self,
    ) -> list[dict[str, Any]]:

        report = self.monitor.analyze()

        tasks: list[
            dict[str, Any]
        ] = []

        issues = report.get(
            "issues",
            [],
        )

        suggestions = report.get(
            "suggestions",
            [],
        )

        for issue in issues:
            text = str(
                issue
            ).strip()

            if not text:
                continue

            tasks.append(
                {
                    "title": (
                        f"Napraw problem: {text}"
                    ),
                    "description": text,
                    "priority": "HIGH",
                    "source": (
                        "project_health_monitor"
                    ),
                    "metadata": {
                        "task_type": "issue",
                        "generated_automatically": True,
                    },
                }
            )

        for suggestion in suggestions:
            text = str(
                suggestion
            ).strip()

            if not text:
                continue

            tasks.append(
                {
                    "title": text,
                    "description": (
                        f"Przeanalizuj i ulepsz: {text}"
                    ),
                    "priority": "NORMAL",
                    "source": (
                        "project_health_monitor"
                    ),
                    "metadata": {
                        "task_type": "suggestion",
                        "generated_automatically": True,
                    },
                }
            )

        self.last_tasks = tasks

        return list(
            tasks
        )

    def summary(
        self,
    ) -> dict[str, Any]:

        return {
            "tasks_count": len(
                self.last_tasks
            ),
            "tasks": list(
                self.last_tasks
            ),
        }
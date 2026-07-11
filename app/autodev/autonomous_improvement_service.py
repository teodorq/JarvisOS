from __future__ import annotations

from typing import Any

from app.autodev.autodev_pipeline import AutoDevPipeline
from app.autodev.autonomous_improvement_pipeline import (
    AutonomousImprovementPipeline,
)


class AutonomousImprovementService:
    """
    Usługa łącząca kolejkę AutoDev z autonomicznym
    pipeline ulepszeń.

    Domyślnie pipeline działa w dry-run, więc samo
    uruchomienie usługi nie zapisuje zmian w kodzie.
    """

    TERMINAL_STATUSES = {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "ROLLED_BACK",
    }

    def __init__(
        self,
        autodev_pipeline: AutoDevPipeline,
        improvement_pipeline: (
            AutonomousImprovementPipeline | None
        ) = None,
        max_tasks: int = 50,
    ) -> None:

        self.autodev_pipeline = autodev_pipeline

        self.improvement_pipeline = (
            improvement_pipeline
            or AutonomousImprovementPipeline()
        )

        self.max_tasks = max(
            1,
            int(max_tasks),
        )

        self.last_result: dict[str, Any] | None = None

    def collect_tasks(
        self,
    ) -> list[dict[str, Any]]:

        tasks = self.autodev_pipeline.list_tasks(
            statuses=None,
            limit=self.max_tasks,
        )

        if not isinstance(
            tasks,
            list,
        ):
            return []

        active_tasks: list[dict[str, Any]] = []

        for task in tasks:
            if not isinstance(
                task,
                dict,
            ):
                continue

            status = str(
                task.get(
                    "status",
                    "",
                )
            ).upper()

            if status in self.TERMINAL_STATUSES:
                continue

            active_tasks.append(
                dict(task)
            )

        return active_tasks

    def run_once(
        self,
        *,
        approved: bool = False,
    ) -> dict[str, Any]:

        tasks = self.collect_tasks()

        result = self.improvement_pipeline.run(
            tasks,
            approved=approved,
        )

        normalized = (
            dict(result)
            if isinstance(
                result,
                dict,
            )
            else {
                "success": False,
                "status": "INVALID_RESULT",
                "error": (
                    "Improvement pipeline zwrócił "
                    "niepoprawny wynik."
                ),
            }
        )

        normalized[
            "collected_tasks"
        ] = len(tasks)

        normalized[
            "approved"
        ] = bool(approved)

        self.last_result = dict(
            normalized
        )

        return normalized

    def preview(
        self,
    ) -> dict[str, Any]:

        return self.run_once(
            approved=False
        )

    def execute_approved(
        self,
    ) -> dict[str, Any]:

        return self.run_once(
            approved=True
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "ready": True,
            "max_tasks": self.max_tasks,
            "last_result": self.last_result,
            "autodev_pipeline": (
                self.autodev_pipeline.status()
            ),
            "improvement_pipeline": (
                self.improvement_pipeline.status()
            ),
        }

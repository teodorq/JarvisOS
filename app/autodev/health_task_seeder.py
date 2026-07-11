from __future__ import annotations

from typing import Any

from app.autodev.autodev_pipeline import AutoDevPipeline
from app.autodev.autonomous_task_queue import TaskPriority
from app.autodev.health_task_generator import HealthTaskGenerator


class HealthTaskSeeder:

    def __init__(
        self,
        pipeline: AutoDevPipeline,
        generator: HealthTaskGenerator | None = None,
    ) -> None:

        self.pipeline = pipeline
        self.generator = generator or HealthTaskGenerator()

    def seed(
        self,
    ) -> dict[str, Any]:

        generated_tasks = self.generator.generate()

        created_tasks: list[dict[str, Any]] = []
        errors: list[str] = []

        for task_data in generated_tasks:
            try:
                priority_name = str(
                    task_data.get(
                        "priority",
                        "NORMAL",
                    )
                ).upper()

                try:
                    priority = TaskPriority(
                        priority_name
                    )
                except ValueError:
                    priority = TaskPriority.NORMAL

                task = self.pipeline.submit(
                    title=str(
                        task_data.get(
                            "title",
                            "AutoDev task",
                        )
                    ),
                    description=str(
                        task_data.get(
                            "description",
                            "",
                        )
                    ),
                    source=str(
                        task_data.get(
                            "source",
                            "health_task_seeder",
                        )
                    ),
                    priority=priority,
                    payload={
                        "goal": str(
                            task_data.get(
                                "description",
                                "",
                            )
                        ),
                        "target": "",
                        "mode": "file",
                        "path": "",
                        "proposed_content": "",
                        "metadata": dict(
                            task_data.get(
                                "metadata",
                                {},
                            )
                        ),
                    },
                    tags=[
                        "autodev",
                        "health",
                        "generated",
                    ],
                    reject_duplicates=True,
                )

                created_tasks.append(
                    task.to_dict()
                )

            except Exception as error:
                errors.append(
                    f"{type(error).__name__}: {error}"
                )

        return {
            "success": not errors,
            "generated_count": len(
                generated_tasks
            ),
            "created_count": len(
                created_tasks
            ),
            "created_tasks": created_tasks,
            "errors": errors,
        }
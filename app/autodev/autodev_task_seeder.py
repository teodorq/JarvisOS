from __future__ import annotations

from typing import Any

from app.autodev.autodev_planner import AutoDevPlanner
from app.autodev.autodev_pipeline import AutoDevPipeline
from app.autodev.autonomous_task_queue import TaskPriority


class AutoDevTaskSeeder:

    def __init__(
        self,
        pipeline: AutoDevPipeline,
        planner: AutoDevPlanner | None = None,
    ) -> None:

        self.pipeline = pipeline
        self.planner = planner or AutoDevPlanner()

    def seed(
        self,
    ) -> dict[str, Any]:

        generated_tasks = self.planner.generate_tasks()

        created_tasks = []
        errors = []

        for task_data in generated_tasks:
            title = str(
                task_data.get(
                    "title",
                    "",
                )
            ).strip()

            description = str(
                task_data.get(
                    "description",
                    "",
                )
            ).strip()

            if not title:
                errors.append(
                    "Pominięto zadanie bez tytułu."
                )
                continue

            try:
                task = self.pipeline.submit(
                    title=title,
                    description=description or title,
                    source="autodev_task_seeder",
                    priority=TaskPriority.NORMAL,
                    payload={
                        "goal": description or title,
                        "target": "",
                        "mode": "file",
                        "path": "",
                        "proposed_content": "",
                        "metadata": {
                            "source": "AutoDevTaskSeeder",
                            "generated_automatically": True,
                        },
                    },
                    tags=[
                        "autodev",
                        "generated",
                        "development",
                    ],
                    reject_duplicates=True,
                )

                created_tasks.append(
                    task.to_dict()
                )

            except Exception as error:
                errors.append(
                    f"{title}: "
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
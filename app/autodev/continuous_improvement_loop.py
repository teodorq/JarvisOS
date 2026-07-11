from __future__ import annotations

from typing import Any

from app.autodev.health_task_generator import (
    HealthTaskGenerator,
)


class ContinuousImprovementLoop:

    def __init__(self) -> None:

        self.generator = HealthTaskGenerator()

        self.completed_cycles = 0
        self.generated_tasks = 0

    def next_cycle(self) -> dict[str, Any]:

        tasks = self.generator.generate()

        self.completed_cycles += 1
        self.generated_tasks += len(tasks)

        return {
            "success": True,
            "cycle": self.completed_cycles,
            "tasks_generated": len(tasks),
            "total_generated": self.generated_tasks,
            "tasks": tasks,
        }

    def status(self) -> dict[str, Any]:

        return {
            "completed_cycles": self.completed_cycles,
            "generated_tasks": self.generated_tasks,
        }
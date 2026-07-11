from dataclasses import dataclass, field
from datetime import datetime

from app.autodev.development_task import (
    DevelopmentTask
)


@dataclass
class DevelopmentPlan:

    goal: str

    tasks: list[
        DevelopmentTask
    ] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_task(
        self,
        task: DevelopmentTask
    ):
        self.tasks.append(task)

    def pending(self):

        return [
            task
            for task in self.tasks
            if task.status == "pending"
        ]

    def completed(self):

        return [
            task
            for task in self.tasks
            if task.status == "completed"
        ]

    def progress(self):

        if not self.tasks:
            return 0

        finished = len(
            self.completed()
        )

        return int(
            finished
            / len(self.tasks)
            * 100
        )

    def summary(self):

        lines = [
            "DEVELOPMENT PLAN",
            f"Cel: {self.goal}",
            f"Postęp: {self.progress()} %",
            ""
        ]

        for task in self.tasks:

            lines.append(
                f"[{task.status}] "
                f"P{task.priority} "
                f"{task.title}"
            )

        return "\n".join(lines)
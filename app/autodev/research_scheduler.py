from dataclasses import dataclass, field
from datetime import datetime

from app.autodev.research_task import (
    ResearchTask
)
from app.autodev.research_prioritizer import (
    ResearchPrioritizer
)


@dataclass
class ScheduledTask:

    task: ResearchTask

    order: int

    scheduled_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    status: str = "scheduled"

    def start(self):

        self.status = "running"

        self.task.start()

    def complete(self):

        self.status = "completed"

        self.task.complete()

    def fail(self):

        self.status = "failed"

        self.task.fail()

    def summary(self):

        return (
            f"[{self.order}] "
            f"{self.task.title} "
            f"({self.status})"
        )


class ResearchScheduler:
    """
    Zarządza kolejką wykonywania
    zadań wygenerowanych przez
    Research Agent.
    """

    def __init__(self):

        self.prioritizer = (
            ResearchPrioritizer()
        )

        self.queue: list[
            ScheduledTask
        ] = []

    def schedule(
        self,
        tasks: list[
            ResearchTask
        ]
    ) -> list[
        ScheduledTask
    ]:

        self.queue.clear()

        ordered = (
            self.prioritizer
            .prioritize(tasks)
        )

        for index, task in enumerate(
            ordered,
            start=1
        ):

            self.queue.append(

                ScheduledTask(

                    task=task,

                    order=index

                )

            )

        return self.queue

    def next_task(self):

        for item in self.queue:

            if item.status == "scheduled":

                return item

        return None

    def completed(self):

        return [

            item

            for item

            in self.queue

            if item.status == "completed"

        ]

    def pending(self):

        return [

            item

            for item

            in self.queue

            if item.status == "scheduled"

        ]

    def running(self):

        return [

            item

            for item

            in self.queue

            if item.status == "running"

        ]

    def progress(self):

        if not self.queue:
            return 0

        return int(

            len(self.completed())

            /

            len(self.queue)

            * 100

        )

    def report(self):

        lines = [

            "RESEARCH SCHEDULER",

            "",

            f"Queue: {len(self.queue)}",

            f"Completed: {len(self.completed())}",

            f"Pending: {len(self.pending())}",

            f"Progress: {self.progress()}%",

            ""

        ]

        if not self.queue:

            lines.append(
                "Brak zadań."
            )

            return "\n".join(
                lines
            )

        for item in self.queue:

            lines.append(
                item.summary()
            )

        return "\n".join(
            lines
        )

    def clear(self):

        self.queue.clear()
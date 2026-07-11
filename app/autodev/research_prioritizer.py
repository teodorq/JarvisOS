from app.autodev.research_task import (
    ResearchTask
)


class ResearchPrioritizer:
    """
    Odpowiada za ustalenie kolejności
    wykonywania zadań wygenerowanych
    przez Research Agent.
    """

    PRIORITY_MAP = {
        "CRITICAL": 100,
        "HIGH": 75,
        "MEDIUM": 50,
        "LOW": 25
    }

    def calculate_score(
        self,
        task: ResearchTask
    ) -> int:

        score = self.PRIORITY_MAP.get(
            task.estimated_risk.upper(),
            0
        )

        score += max(
            0,
            10 - task.priority
        ) * 5

        if task.requires_backup:
            score += 2

        if task.requires_validation:
            score += 2

        if task.requires_approval:
            score += 1

        if task.task_type == "refactor":
            score += 10

        return score

    def prioritize(
        self,
        tasks: list[ResearchTask]
    ) -> list[ResearchTask]:

        return sorted(
            tasks,
            key=lambda task: (
                self.calculate_score(task),
                -task.priority
            ),
            reverse=True
        )

    def report(
        self,
        tasks: list[ResearchTask]
    ) -> str:

        ordered = self.prioritize(
            tasks
        )

        lines = [
            "RESEARCH PRIORITIZER",
            ""
        ]

        for index, task in enumerate(
            ordered,
            start=1
        ):

            lines.append(
                f"{index}. {task.title}"
            )

            lines.append(
                f"   Score: {self.calculate_score(task)}"
            )

            lines.append(
                f"   Risk: {task.estimated_risk}"
            )

            lines.append(
                f"   Target: {task.target}"
            )

            lines.append("")

        return "\n".join(
            lines
        )
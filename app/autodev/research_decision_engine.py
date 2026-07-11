from dataclasses import dataclass, field
from datetime import datetime

from app.autodev.research_task import (
    ResearchTask
)


@dataclass
class Decision:

    task: ResearchTask

    action: str

    reason: str

    confidence: float

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    def summary(self):

        return (
            f"[{self.action}] "
            f"{self.task.title} "
            f"({self.confidence:.2f})"
        )


class ResearchDecisionEngine:
    """
    Podejmuje decyzję co zrobić
    z zadaniem wygenerowanym
    przez Research Agent.
    """

    def decide(
        self,
        task: ResearchTask
    ) -> Decision:

        risk = (
            task.estimated_risk.upper()
        )

        if risk == "CRITICAL":

            return Decision(

                task=task,

                action="EXECUTE_FIRST",

                reason=(
                    "Najwyższy priorytet."
                ),

                confidence=0.99

            )

        if risk == "HIGH":

            return Decision(

                task=task,

                action="EXECUTE",

                reason=(
                    "Wysoki wpływ na projekt."
                ),

                confidence=0.95

            )

        if risk == "MEDIUM":

            return Decision(

                task=task,

                action="QUEUE",

                reason=(
                    "Może poczekać."
                ),

                confidence=0.85

            )

        return Decision(

            task=task,

            action="DEFER",

            reason=(
                "Niski priorytet."
            ),

            confidence=0.70

        )

    def decide_many(
        self,
        tasks: list[
            ResearchTask
        ]
    ) -> list[
        Decision
    ]:

        decisions = [

            self.decide(task)

            for task

            in tasks

        ]

        decisions.sort(

            key=lambda d:
                d.confidence,

            reverse=True

        )

        return decisions

    def report(
        self,
        tasks: list[
            ResearchTask
        ]
    ) -> str:

        decisions = (
            self.decide_many(
                tasks
            )
        )

        lines = [

            "DECISION ENGINE",

            ""

        ]

        for decision in decisions:

            lines.append(

                decision.summary()

            )

            lines.append(

                f"Reason: "

                f"{decision.reason}"

            )

            lines.append("")

        return "\n".join(
            lines
        )
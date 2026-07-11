from dataclasses import dataclass, field
from datetime import datetime

from app.autodev.reasoning_step import (
    ReasoningStep
)


@dataclass
class ReasoningResult:

    goal: str

    summary: str = ""

    confidence: float = 0.0

    steps: list[
        ReasoningStep
    ] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_step(
        self,
        step: ReasoningStep
    ):
        self.steps.append(step)

    def report(self):

        lines = [
            "AI REASONER",
            f"Cel: {self.goal}",
            f"Confidence: {self.confidence:.2f}",
            ""
        ]

        for step in self.steps:

            lines.append(
                f"[{step.status}] {step.title}"
            )

        if self.summary:
            lines.append("")
            lines.append(self.summary)

        return "\n".join(lines)
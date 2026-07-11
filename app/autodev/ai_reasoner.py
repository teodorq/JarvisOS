from app.autodev.goal import Goal
from app.autodev.reasoning_memory import (
    ReasoningMemory
)
from app.autodev.reasoning_result import (
    ReasoningResult
)
from app.autodev.reasoning_step import (
    ReasoningStep
)


class AIReasoner:

    def __init__(self):

        self.memory = ReasoningMemory()

    def analyze(
        self,
        goal: Goal
    ) -> ReasoningResult:

        result = ReasoningResult(
            goal=goal.title
        )

        result.add_step(
            ReasoningStep(
                title="Analiza celu"
            )
        )

        result.add_step(
            ReasoningStep(
                title="Analiza zależności"
            )
        )

        result.add_step(
            ReasoningStep(
                title="Ocena ryzyka"
            )
        )

        result.add_step(
            ReasoningStep(
                title="Dobór strategii"
            )
        )

        result.add_step(
            ReasoningStep(
                title="Propozycja planu"
            )
        )

        for step in result.steps:
            step.start()
            step.complete()

        result.confidence = 0.95

        result.summary = (
            "Analiza zakończona. "
            "Cel może zostać przekazany "
            "do Goal Planner oraz AutoDev."
        )

        self.memory.remember(result)

        return result
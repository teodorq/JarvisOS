from datetime import datetime

from app.autodev.research_result import (
    ResearchResult
)


class ResearchMemory:

    """
    Przechowuje historię analiz wykonanych
    przez Research Agent.
    """

    def __init__(self):

        self.history = []

        self.created_at = (
            datetime.now().isoformat()
        )

    def remember(
        self,
        result: ResearchResult
    ):

        self.history.append(
            result
        )

    def last(
        self
    ):

        if not self.history:
            return None

        return self.history[-1]

    def first(
        self
    ):

        if not self.history:
            return None

        return self.history[0]

    def count(
        self
    ) -> int:

        return len(
            self.history
        )

    def clear(
        self
    ):

        self.history.clear()

    def successful(
        self
    ):

        return [

            result

            for result

            in self.history

            if result.success

        ]

    def failed(
        self
    ):

        return [

            result

            for result

            in self.history

            if not result.success

        ]

    def average_findings(
        self
    ) -> float:

        if not self.history:
            return 0.0

        total = sum(
            result.count()

            for result

            in self.history
        )

        return (
            total
            / len(self.history)
        )

    def report(
        self
    ) -> str:

        lines = [

            "RESEARCH MEMORY",

            "",

            f"Analiz: {self.count()}",

            f"Udanych: {len(self.successful())}",

            f"Błędnych: {len(self.failed())}",

            f"Średnia liczba wyników: "
            f"{self.average_findings():.2f}",

            ""
        ]

        if not self.history:

            lines.append(
                "Brak historii."
            )

            return "\n".join(
                lines
            )

        lines.append(
            "Ostatnie analizy:"
        )

        for result in self.history[-10:]:

            lines.append(

                f"- {result.goal}"

                f" "

                f"({result.count()} wyników)"

            )

        return "\n".join(
            lines
        )
from dataclasses import dataclass, field
from datetime import datetime

from app.autodev.research_finding import (
    ResearchFinding
)


@dataclass
class ResearchResult:
    """
    Wynik pełnego badania projektu.
    Zawiera wszystkie znalezione elementy
    oraz końcowe podsumowanie.
    """

    goal: str

    findings: list[
        ResearchFinding
    ] = field(
        default_factory=list
    )

    duration: float = 0.0

    success: bool = True

    summary_text: str = ""

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    def add(
        self,
        finding: ResearchFinding
    ):

        self.findings.append(
            finding
        )

    def count(
        self
    ) -> int:

        return len(
            self.findings
        )

    def sort(
        self
    ):

        self.findings.sort(
            key=lambda finding:
                finding.score,
            reverse=True
        )

    def best(
        self,
        limit: int = 10
    ):

        self.sort()

        return self.findings[
            :limit
        ]

    def categories(
        self
    ) -> dict:

        result = {}

        for finding in self.findings:

            category = (
                finding.category
            )

            result.setdefault(
                category,
                0
            )

            result[
                category
            ] += 1

        return result

    def total_score(
        self
    ) -> float:

        return sum(
            finding.score
            for finding
            in self.findings
        )

    def average_score(
        self
    ) -> float:

        if not self.findings:
            return 0.0

        return (
            self.total_score()
            / len(self.findings)
        )

    def report(
        self
    ) -> str:

        self.sort()

        lines = [

            "RESEARCH RESULT",
            "",

            f"Goal: {self.goal}",

            f"Success: {self.success}",

            f"Findings: {self.count()}",

            f"Average Score: "
            f"{self.average_score():.2f}",

            f"Duration: "
            f"{self.duration:.2f}s",

            ""
        ]

        if self.summary_text:

            lines.append(
                self.summary_text
            )

            lines.append("")

        lines.append(
            "Top Results:"
        )

        if not self.findings:

            lines.append(
                "Brak wyników."
            )

        else:

            for finding in self.best():

                lines.append(

                    f"[{finding.score:5.1f}] "

                    f"{finding.title}"

                    f" "

                    f"({finding.category})"

                )

        lines.append("")
        lines.append(
            "Categories:"
        )

        categories = (
            self.categories()
        )

        if not categories:

            lines.append(
                "Brak."
            )

        else:

            for (
                category,
                amount
            ) in sorted(
                categories.items()
            ):

                lines.append(

                    f"- {category}: "

                    f"{amount}"

                )

        return "\n".join(
            lines
        )
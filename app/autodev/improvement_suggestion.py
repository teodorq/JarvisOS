from dataclasses import dataclass, field

from app.autodev.problem_detector import (
    DetectedProblem
)


@dataclass
class ImprovementSuggestion:

    module: str

    priority: str

    title: str

    description: str

    estimated_benefit: str

    actions: list[str] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )

    def add_action(
        self,
        action: str
    ):

        action = action.strip()

        if (
            action
            and action not in self.actions
        ):
            self.actions.append(
                action
            )

    def summary(
        self
    ) -> str:

        lines = [

            "IMPROVEMENT SUGGESTION",

            "",

            f"Module: {self.module}",

            f"Priority: {self.priority}",

            f"Title: {self.title}",

            "",

            self.description,

            "",

            f"Benefit: {self.estimated_benefit}"

        ]

        if self.actions:

            lines.append("")
            lines.append("Actions:")

            for action in self.actions:

                lines.append(
                    f"- {action}"
                )

        return "\n".join(
            lines
        )


class ImprovementSuggestionEngine:

    """
    Tworzy propozycje zmian
    na podstawie wykrytych problemów.
    """

    def generate(
        self,
        problems: list[
            DetectedProblem
        ]
    ) -> list[
        ImprovementSuggestion
    ]:

        suggestions = []

        for problem in problems:

            suggestion = (
                ImprovementSuggestion(

                    module=problem.module,

                    priority=problem.severity,

                    title=problem.title,

                    description=problem.description,

                    estimated_benefit="Unknown"

                )
            )

            title = (
                problem.title.lower()
            )

            if "duży plik" in title:

                suggestion.estimated_benefit = (
                    "-30% rozmiaru modułu"
                )

                suggestion.add_action(
                    "Podziel plik na mniejsze moduły."
                )

                suggestion.add_action(
                    "Wydziel logikę do osobnych klas."
                )

            elif "funkcji" in title:

                suggestion.estimated_benefit = (
                    "Lepsza czytelność"
                )

                suggestion.add_action(
                    "Podziel funkcje według odpowiedzialności."
                )

            elif "import" in title:

                suggestion.estimated_benefit = (
                    "Mniejsze sprzężenie"
                )

                suggestion.add_action(
                    "Usuń nieużywane importy."
                )

                suggestion.add_action(
                    "Rozdziel zależności."
                )

            elif "sprzężenie" in title:

                suggestion.estimated_benefit = (
                    "Luźniejsza architektura"
                )

                suggestion.add_action(
                    "Wprowadź warstwę pośrednią."
                )

            elif "jakość" in title:

                suggestion.estimated_benefit = (
                    "Duża poprawa jakości"
                )

                suggestion.add_action(
                    "Przeprowadź refaktoryzację modułu."
                )

                suggestion.add_action(
                    "Podziel odpowiedzialności."
                )

                suggestion.add_action(
                    "Zmniejsz zależności."
                )

            else:

                suggestion.estimated_benefit = (
                    "Poprawa jakości kodu"
                )

                suggestion.add_action(
                    problem.recommendation
                )

            suggestions.append(
                suggestion
            )

        return suggestions

    def report(
        self,
        suggestions: list[
            ImprovementSuggestion
        ]
    ) -> str:

        lines = [

            "IMPROVEMENT SUGGESTIONS",

            "",

            f"Suggestions: {len(suggestions)}",

            ""
        ]

        if not suggestions:

            lines.append(
                "Brak sugestii."
            )

            return "\n".join(
                lines
            )

        for suggestion in suggestions:

            lines.append(
                f"[{suggestion.priority}] "
                f"{suggestion.module}"
            )

            lines.append(
                f"  {suggestion.title}"
            )

            lines.append(
                f"  Benefit: "
                f"{suggestion.estimated_benefit}"
            )

            lines.append("")

        return "\n".join(
            lines
        )
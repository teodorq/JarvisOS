from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class ResearchQuery:
    """
    Reprezentuje pojedyncze zadanie badawcze
    wykonywane przez Research Agent.
    """

    goal: str

    keywords: List[str] = field(
        default_factory=list
    )

    categories: List[str] = field(
        default_factory=list
    )

    excluded_categories: List[str] = field(
        default_factory=list
    )

    search_classes: bool = True

    search_functions: bool = True

    search_imports: bool = True

    search_paths: bool = True

    max_results: int = 50

    metadata: Dict = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    def add_keyword(
        self,
        keyword: str
    ):

        keyword = keyword.strip()

        if (
            keyword
            and keyword not in self.keywords
        ):
            self.keywords.append(
                keyword
            )

    def add_category(
        self,
        category: str
    ):

        category = category.strip().lower()

        if (
            category
            and category not in self.categories
        ):
            self.categories.append(
                category
            )

    def exclude_category(
        self,
        category: str
    ):

        category = category.strip().lower()

        if (
            category
            and category not in
            self.excluded_categories
        ):
            self.excluded_categories.append(
                category
            )

    def remove_keyword(
        self,
        keyword: str
    ):

        if keyword in self.keywords:
            self.keywords.remove(
                keyword
            )

    def clear_keywords(
        self
    ):

        self.keywords.clear()

    def has_keyword(
        self,
        keyword: str
    ) -> bool:

        return (
            keyword in self.keywords
        )

    def validate(
        self
    ) -> tuple[bool, list[str]]:

        errors = []

        if not self.goal.strip():
            errors.append(
                "Cel Research Agent jest pusty."
            )

        if self.max_results <= 0:
            errors.append(
                "max_results musi być większe od zera."
            )

        return (
            len(errors) == 0,
            errors
        )

    def summary(
        self
    ) -> str:

        lines = [
            "RESEARCH QUERY",
            "",
            f"Goal: {self.goal}",
            "",
            "Keywords:"
        ]

        if self.keywords:

            for keyword in self.keywords:

                lines.append(
                    f" - {keyword}"
                )

        else:

            lines.append(
                " - brak"
            )

        lines.append("")
        lines.append("Categories:")

        if self.categories:

            for category in self.categories:

                lines.append(
                    f" - {category}"
                )

        else:

            lines.append(
                " - wszystkie"
            )

        if self.excluded_categories:

            lines.append("")
            lines.append(
                "Excluded:"
            )

            for category in (
                self.excluded_categories
            ):

                lines.append(
                    f" - {category}"
                )

        lines.append("")
        lines.append(
            f"Search classes: {self.search_classes}"
        )

        lines.append(
            f"Search functions: {self.search_functions}"
        )

        lines.append(
            f"Search imports: {self.search_imports}"
        )

        lines.append(
            f"Search paths: {self.search_paths}"
        )

        lines.append(
            f"Max results: {self.max_results}"
        )

        return "\n".join(
            lines
        )
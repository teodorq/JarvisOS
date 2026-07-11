from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ResearchStrategy:
    """
    Określa sposób prowadzenia analizy
    przez Research Agent.
    """

    name: str

    description: str = ""

    priority: int = 5

    max_files: int = 50

    max_depth: int = 5

    use_semantic_search: bool = True

    use_project_scanner: bool = True

    use_code_reader: bool = True

    use_knowledge_graph: bool = True

    use_reasoner: bool = False

    stop_after_first_match: bool = False

    allowed_categories: list[str] = field(
        default_factory=list
    )

    excluded_categories: list[str] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    def allow_category(
        self,
        category: str
    ):

        category = category.lower().strip()

        if (
            category
            and category
            not in self.allowed_categories
        ):
            self.allowed_categories.append(
                category
            )

    def exclude_category(
        self,
        category: str
    ):

        category = category.lower().strip()

        if (
            category
            and category
            not in self.excluded_categories
        ):
            self.excluded_categories.append(
                category
            )

    def is_allowed(
        self,
        category: str
    ) -> bool:

        category = category.lower()

        if (
            category
            in self.excluded_categories
        ):
            return False

        if not self.allowed_categories:
            return True

        return (
            category
            in self.allowed_categories
        )

    def summary(
        self
    ) -> str:

        lines = [

            "RESEARCH STRATEGY",

            "",

            f"Name: {self.name}",

            f"Priority: {self.priority}",

            f"Max files: {self.max_files}",

            f"Max depth: {self.max_depth}",

            ""

        ]

        lines.append(
            f"Semantic Search: "
            f"{self.use_semantic_search}"
        )

        lines.append(
            f"Project Scanner: "
            f"{self.use_project_scanner}"
        )

        lines.append(
            f"Code Reader: "
            f"{self.use_code_reader}"
        )

        lines.append(
            f"Knowledge Graph: "
            f"{self.use_knowledge_graph}"
        )

        lines.append(
            f"Reasoner: "
            f"{self.use_reasoner}"
        )

        lines.append(
            f"Stop After First: "
            f"{self.stop_after_first_match}"
        )

        if self.allowed_categories:

            lines.append("")
            lines.append(
                "Allowed:"
            )

            for category in (
                self.allowed_categories
            ):

                lines.append(
                    f"- {category}"
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
                    f"- {category}"
                )

        return "\n".join(
            lines
        )
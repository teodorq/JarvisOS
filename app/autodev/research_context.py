from dataclasses import dataclass, field
from datetime import datetime

from app.autodev.project_index import (
    ProjectIndex
)
from app.autodev.module_graph import (
    ModuleGraph
)
from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_result import (
    ResearchResult
)


@dataclass
class ResearchContext:
    """
    Pełny kontekst pracy Research Agent.
    Łączy wszystkie dane potrzebne
    do analizy projektu.
    """

    query: ResearchQuery | None = None

    result: ResearchResult | None = None

    project_index: ProjectIndex | None = None

    knowledge_graph: ModuleGraph | None = None

    search_results: list = field(
        default_factory=list
    )

    analyzed_files: list[str] = field(
        default_factory=list
    )

    skipped_files: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    def add_file(
        self,
        path: str
    ):

        if (
            path
            and path not in
            self.analyzed_files
        ):
            self.analyzed_files.append(
                path
            )

    def skip_file(
        self,
        path: str
    ):

        if (
            path
            and path not in
            self.skipped_files
        ):
            self.skipped_files.append(
                path
            )

    def add_warning(
        self,
        warning: str
    ):

        warning = warning.strip()

        if (
            warning
            and warning
            not in self.warnings
        ):
            self.warnings.append(
                warning
            )

    def analyzed_count(
        self
    ) -> int:

        return len(
            self.analyzed_files
        )

    def skipped_count(
        self
    ) -> int:

        return len(
            self.skipped_files
        )

    def summary(
        self
    ) -> str:

        lines = [

            "RESEARCH CONTEXT",

            "",

            f"Analyzed files: "
            f"{self.analyzed_count()}",

            f"Skipped files: "
            f"{self.skipped_count()}",

            f"Search results: "
            f"{len(self.search_results)}",

            ""
        ]

        if self.query:

            lines.append(
                f"Goal: {self.query.goal}"
            )

        if self.result:

            lines.append(
                f"Findings: "
                f"{self.result.count()}"
            )

        if self.warnings:

            lines.append("")
            lines.append(
                "Warnings:"
            )

            for warning in self.warnings:

                lines.append(
                    f"- {warning}"
                )

        return "\n".join(
            lines
        )
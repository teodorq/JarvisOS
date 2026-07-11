from dataclasses import dataclass, field
from datetime import datetime

from app.autodev.research_memory import (
    ResearchMemory
)
from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_result import (
    ResearchResult
)


@dataclass
class ResearchSession:
    """
    Reprezentuje jedną sesję pracy
    Research Agenta.
    """

    session_id: str = field(
        default_factory=lambda:
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    started_at: str = field(
        default_factory=lambda:
        datetime.now().isoformat()
    )

    finished_at: str = ""

    status: str = "idle"

    current_query: ResearchQuery | None = None

    current_result: ResearchResult | None = None

    memory: ResearchMemory = field(
        default_factory=ResearchMemory
    )

    def start(
        self,
        query: ResearchQuery
    ):

        self.current_query = query

        self.current_result = None

        self.status = "running"

    def finish(
        self,
        result: ResearchResult
    ):

        self.current_result = result

        self.memory.remember(
            result
        )

        self.finished_at = (
            datetime.now().isoformat()
        )

        self.status = "finished"

    def fail(
        self
    ):

        self.finished_at = (
            datetime.now().isoformat()
        )

        self.status = "failed"

    def reset(
        self
    ):

        self.current_query = None

        self.current_result = None

        self.finished_at = ""

        self.status = "idle"

    def is_running(
        self
    ) -> bool:

        return (
            self.status == "running"
        )

    def has_result(
        self
    ) -> bool:

        return (
            self.current_result
            is not None
        )

    def summary(
        self
    ) -> str:

        lines = [

            "RESEARCH SESSION",

            "",

            f"Session ID: {self.session_id}",

            f"Status: {self.status}",

            f"Started: {self.started_at}",

            f"Finished: "
            f"{self.finished_at or '-'}",

            ""
        ]

        if self.current_query:

            lines.append(
                "Current Query:"
            )

            lines.append(
                self.current_query.goal
            )

            lines.append("")

        if self.current_result:

            lines.append(
                "Last Result:"
            )

            lines.append(
                f"{self.current_result.count()} "
                f"znalezionych plików."
            )

            lines.append("")

        lines.append(
            self.memory.report()
        )

        return "\n".join(
            lines
        )
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AutoDevContext:

    goal: str = ""

    project_index = None

    knowledge_graph = None

    search_results: list = field(
        default_factory=list
    )

    reasoning = None

    development_plan = None

    workflow_result = None

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def summary(self):

        return "\n".join([
            "AUTODEV CONTEXT",
            f"Goal: {self.goal}",
            f"Search Results: {len(self.search_results)}"
        ])
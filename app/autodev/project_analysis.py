from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProjectAnalysis:

    goal: str

    dependencies: list[str] = field(
        default_factory=list
    )

    imports: list[str] = field(
        default_factory=list
    )

    references: list[str] = field(
        default_factory=list
    )

    impacted_files: list[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def summary(self):

        return "\n".join([
            "PROJECT ANALYSIS",
            f"Goal: {self.goal}",
            f"Dependencies: {len(self.dependencies)}",
            f"Imports: {len(self.imports)}",
            f"References: {len(self.references)}",
            f"Impacted Files: {len(self.impacted_files)}"
        ])
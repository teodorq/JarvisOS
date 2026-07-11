from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Goal:

    title: str

    description: str = ""

    priority: int = 5

    category: str = "development"

    status: str = "new"

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    metadata: dict = field(
        default_factory=dict
    )

    def start(self):
        self.status = "planning"

    def complete(self):
        self.status = "completed"

    def fail(self):
        self.status = "failed"

    def summary(self):

        return "\n".join([
            "GOAL",
            f"Tytuł: {self.title}",
            f"Opis: {self.description}",
            f"Kategoria: {self.category}",
            f"Priorytet: {self.priority}",
            f"Status: {self.status}"
        ])
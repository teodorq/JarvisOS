from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DevelopmentTask:

    title: str

    description: str = ""

    target: str = ""

    priority: int = 5

    estimated_minutes: int = 10

    status: str = "pending"

    metadata: dict = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def start(self):
        self.status = "running"

    def complete(self):
        self.status = "completed"

    def fail(self):
        self.status = "failed"

    def summary(self):

        return "\n".join([
            "TASK",
            f"Tytuł: {self.title}",
            f"Target: {self.target}",
            f"Priorytet: {self.priority}",
            f"Status: {self.status}",
            f"Czas: {self.estimated_minutes} min"
        ])
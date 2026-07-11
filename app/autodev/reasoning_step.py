from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReasoningStep:

    title: str

    description: str = ""

    status: str = "pending"

    confidence: float = 1.0

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
            "REASONING STEP",
            f"Tytuł: {self.title}",
            f"Status: {self.status}",
            f"Confidence: {self.confidence:.2f}"
        ])
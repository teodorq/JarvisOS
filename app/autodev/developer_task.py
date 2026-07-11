from dataclasses import dataclass, field
from typing import List


@dataclass
class DeveloperStep:
    index: int
    name: str
    description: str
    action_type: str
    target: str = ""
    status: str = "pending"
    result: str = ""
    error: str = ""

    def start(self):
        self.status = "running"

    def complete(self, result: str = ""):
        self.status = "completed"
        self.result = result

    def fail(self, error: str):
        self.status = "failed"
        self.error = error


@dataclass
class DeveloperTask:
    goal: str
    target: str = ""
    steps: List[DeveloperStep] = field(default_factory=list)
    current_step: int = 0
    finished: bool = False
    failed: bool = False

    def add_step(
        self,
        name: str,
        description: str,
        action_type: str,
        target: str = ""
    ):
        step = DeveloperStep(
            index=len(self.steps) + 1,
            name=name,
            description=description,
            action_type=action_type,
            target=target
        )

        self.steps.append(step)
        return step

    def get_current_step(self):
        if self.current_step >= len(self.steps):
            return None

        return self.steps[self.current_step]

    def complete_current_step(self, result: str = ""):
        step = self.get_current_step()

        if step is None:
            self.finished = True
            return

        step.complete(result)
        self.current_step += 1

        if self.current_step >= len(self.steps):
            self.finished = True

    def fail_current_step(self, error: str):
        step = self.get_current_step()

        if step is not None:
            step.fail(error)

        self.failed = True
        self.finished = True

    def summary(self) -> str:
        lines = [
            "DEVELOPER TASK",
            f"Cel: {self.goal}",
            f"Target: {self.target or 'brak'}",
            f"Status: {'FAILED' if self.failed else 'FINISHED' if self.finished else 'RUNNING'}",
            "",
            "Kroki:"
        ]

        icons = {
            "pending": "⬜",
            "running": "🔄",
            "completed": "✅",
            "failed": "❌"
        }

        for step in self.steps:
            icon = icons.get(step.status, "⬜")

            lines.append(
                f"{icon} {step.index}. {step.name} — {step.description}"
            )

            if step.result:
                lines.append(f"   Wynik: {step.result}")

            if step.error:
                lines.append(f"   Błąd: {step.error}")

        return "\n".join(lines)
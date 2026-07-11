from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class AgentStep:
    index: int
    instruction: str
    action_type: str = "unknown"
    target: str = ""
    text: str = ""
    url: str = ""
    query: str = ""

    done: bool = False
    failed: bool = False
    result: str = ""

    attempts: int = 0
    max_attempts: int = 2

    feedback_success: bool = True
    feedback_confidence: float = 0.0
    feedback_reason: str = ""
    next_hint: str = ""

    def can_retry(self) -> bool:
        return self.attempts < self.max_attempts


@dataclass
class AgentTask:
    command: str
    goal: str
    steps: List[AgentStep] = field(default_factory=list)
    current_step: int = 0
    finished: bool = False
    failed: bool = False
    history: List[Dict[str, Any]] = field(default_factory=list)

    def get_current_step(self):
        if self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def mark_step_attempt(self):
        step = self.get_current_step()

        if step:
            step.attempts += 1

    def mark_step_done(self, result: str):
        step = self.get_current_step()

        if step:
            step.done = True
            step.failed = False
            step.result = result

            self.history.append({
                "step": step.index,
                "instruction": step.instruction,
                "result": result,
                "attempts": step.attempts,
                "status": "done"
            })

        self.current_step += 1

        if self.current_step >= len(self.steps):
            self.finished = True

    def mark_step_retry(self, reason: str = "", next_hint: str = ""):
        step = self.get_current_step()

        if step:
            step.done = False
            step.failed = False
            step.feedback_reason = reason
            step.next_hint = next_hint

            self.history.append({
                "step": step.index,
                "instruction": step.instruction,
                "reason": reason,
                "next_hint": next_hint,
                "attempts": step.attempts,
                "status": "retry"
            })

    def mark_step_failed(self, result: str):
        step = self.get_current_step()

        if step:
            step.failed = True
            step.done = False
            step.result = result

            self.history.append({
                "step": step.index,
                "instruction": step.instruction,
                "result": result,
                "attempts": step.attempts,
                "status": "failed"
            })

        self.failed = True
        self.finished = True

    def mark_failed(self, result: str):
        self.failed = True
        self.finished = True

        self.history.append({
            "step": self.current_step,
            "result": result,
            "status": "failed"
        })

    def summary(self) -> str:
        lines = [f"Cel: {self.goal}", "Kroki:"]

        for step in self.steps:
            if step.done:
                status = "✅"
            elif step.failed:
                status = "❌"
            else:
                status = "⬜"

            lines.append(
                f"{status} {step.index}. {step.instruction} "
                f"(próby: {step.attempts}/{step.max_attempts})"
            )

        return "\n".join(lines)
import json
from pathlib import Path


class GoalManager:

    def __init__(self):
        self.memory_file = Path("data/memory/goals.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

        self.current_goal = None
        self.status = "idle"
        self.notes = []
        self.completed_steps = []
        self.failed_steps = []

        self.load()

    def start_goal(self, goal: str):
        self.current_goal = goal
        self.status = "running"
        self.notes = []
        self.completed_steps = []
        self.failed_steps = []
        self.save()

    def complete_step(self, step, result: str):
        self.completed_steps.append({
            "index": step.index,
            "instruction": step.instruction,
            "result": result
        })
        self.save()

    def fail_step(self, step, reason: str):
        self.failed_steps.append({
            "index": step.index,
            "instruction": step.instruction,
            "reason": reason
        })
        self.save()

    def add_note(self, note: str):
        if note:
            self.notes.append(note)
            self.save()

    def finish_goal(self):
        self.status = "finished"
        self.save()

    def fail_goal(self):
        self.status = "failed"
        self.save()

    def save(self):
        data = {
            "current_goal": self.current_goal,
            "status": self.status,
            "notes": self.notes,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps
        }

        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load(self):
        if not self.memory_file.exists():
            return

        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.current_goal = data.get("current_goal")
            self.status = data.get("status", "idle")
            self.notes = data.get("notes", [])
            self.completed_steps = data.get("completed_steps", [])
            self.failed_steps = data.get("failed_steps", [])

        except Exception:
            pass

    def summary(self):
        lines = [
            "GOAL MANAGER",
            f"Cel: {self.current_goal}",
            f"Status: {self.status}",
            f"Ukończone: {len(self.completed_steps)}",
            f"Nieudane: {len(self.failed_steps)}"
        ]

        if self.notes:
            lines.append("")
            lines.append("Notatki:")

            for note in self.notes[-5:]:
                lines.append(f"- {note}")

        return "\n".join(lines)
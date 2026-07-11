import json
from pathlib import Path


class SelfReflection:

    def __init__(self):
        self.memory_file = Path("data/memory/reflections.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

        self.history = []
        self.load()

    def reflect(self, task, goal_manager):
        reflection = {
            "goal": task.goal,
            "finished": task.finished,
            "failed": task.failed,
            "completed_steps": len(goal_manager.completed_steps),
            "failed_steps": len(goal_manager.failed_steps),
            "notes": list(goal_manager.notes),
            "summary": self._build_summary(task, goal_manager)
        }

        self.history.append(reflection)

        if len(self.history) > 100:
            self.history = self.history[-100:]

        self.save()

        return reflection

    def _build_summary(self, task, goal_manager):
        if task.failed:
            return (
                f"Nie udało się ukończyć celu "
                f"'{task.goal}'. "
                f"Poprawnie wykonano "
                f"{len(goal_manager.completed_steps)} kroków."
            )

        return (
            f"Cel '{task.goal}' został ukończony. "
            f"Wykonano "
            f"{len(goal_manager.completed_steps)} kroków."
        )

    def last(self):
        if not self.history:
            return None

        return self.history[-1]

    def save(self):
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(
                self.history,
                file,
                indent=4,
                ensure_ascii=False
            )

    def load(self):
        if not self.memory_file.exists():
            return

        try:
            with open(self.memory_file, "r", encoding="utf-8") as file:
                self.history = json.load(file)
        except Exception:
            self.history = []

    def summary(self):
        if not self.history:
            return "Brak historii refleksji."

        last = self.last()

        lines = [
            "SELF REFLECTION",
            "",
            f"Cel: {last['goal']}",
            f"Ukończono: {not last['failed']}",
            f"Kroki wykonane: {last['completed_steps']}",
            f"Kroki nieudane: {last['failed_steps']}",
            "",
            last["summary"]
        ]

        return "\n".join(lines)
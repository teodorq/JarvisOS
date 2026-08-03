from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class SelfReflection:

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        memory_file: str | Path | None = None,
    ) -> None:
        paths = ProjectPaths.from_value(
            project_root
        )
        self.memory_file = (
            Path(memory_file)
            if memory_file is not None
            else paths.reflection_memory_file
        ).expanduser().resolve(
            strict=False
        )
        self._store = JsonStore(
            self.memory_file,
            list,
        )
        self.history: list[dict[str, Any]] = []
        self.load()

    def reflect(
        self,
        task,
        goal_manager,
    ):
        reflection = {
            "goal": task.goal,
            "finished": task.finished,
            "failed": task.failed,
            "completed_steps": len(
                goal_manager.completed_steps
            ),
            "failed_steps": len(
                goal_manager.failed_steps
            ),
            "notes": list(
                goal_manager.notes
            ),
            "summary": self._build_summary(
                task,
                goal_manager,
            ),
        }

        self.history.append(
            reflection
        )

        if len(self.history) > 100:
            self.history = self.history[-100:]

        self.save()
        return reflection

    def _build_summary(
        self,
        task,
        goal_manager,
    ):
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

    def last(
        self,
    ):
        if not self.history:
            return None

        return self.history[-1]

    def save(
        self,
    ):
        self._store.save(
            self.history
        )

    def load(
        self,
    ):
        data = self._store.load()

        if isinstance(
            data,
            list,
        ):
            self.history = data
        else:
            self.history = []

    def summary(
        self,
    ):
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
            last["summary"],
        ]

        return "\n".join(
            lines
        )

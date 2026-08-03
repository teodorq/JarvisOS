from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class GoalManager:

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
            else paths.goal_memory_file
        ).expanduser().resolve(
            strict=False
        )
        self._store = JsonStore(
            self.memory_file,
            self._default_state,
        )

        self.current_goal = None
        self.status = "idle"
        self.notes = []
        self.completed_steps = []
        self.failed_steps = []
        self.load()

    @staticmethod
    def _default_state(
    ) -> dict[str, Any]:
        return {
            "current_goal": None,
            "status": "idle",
            "notes": [],
            "completed_steps": [],
            "failed_steps": [],
        }

    def start_goal(
        self,
        goal: str,
    ):
        self.current_goal = goal
        self.status = "running"
        self.notes = []
        self.completed_steps = []
        self.failed_steps = []
        self.save()

    def complete_step(
        self,
        step,
        result: str,
    ):
        self.completed_steps.append(
            {
                "index": step.index,
                "instruction": step.instruction,
                "result": result,
            }
        )
        self.save()

    def fail_step(
        self,
        step,
        reason: str,
    ):
        self.failed_steps.append(
            {
                "index": step.index,
                "instruction": step.instruction,
                "reason": reason,
            }
        )
        self.save()

    def add_note(
        self,
        note: str,
    ):
        if note:
            self.notes.append(
                note
            )
            self.save()

    def finish_goal(
        self,
    ):
        self.status = "finished"
        self.save()

    def fail_goal(
        self,
    ):
        self.status = "failed"
        self.save()

    def save(
        self,
    ):
        self._store.save(
            {
                "current_goal": self.current_goal,
                "status": self.status,
                "notes": self.notes,
                "completed_steps": self.completed_steps,
                "failed_steps": self.failed_steps,
            }
        )

    def load(
        self,
    ):
        data = self._store.load()

        if not isinstance(
            data,
            dict,
        ):
            data = self._default_state()

        self.current_goal = data.get(
            "current_goal"
        )
        self.status = data.get(
            "status",
            "idle",
        )
        self.notes = list(
            data.get(
                "notes",
                [],
            )
            or []
        )
        self.completed_steps = list(
            data.get(
                "completed_steps",
                [],
            )
            or []
        )
        self.failed_steps = list(
            data.get(
                "failed_steps",
                [],
            )
            or []
        )

    def summary(
        self,
    ):
        lines = [
            "GOAL MANAGER",
            f"Cel: {self.current_goal}",
            f"Status: {self.status}",
            f"Ukończone: {len(self.completed_steps)}",
            f"Nieudane: {len(self.failed_steps)}",
        ]

        if self.notes:
            lines.extend(
                [
                    "",
                    "Notatki:",
                ]
            )

            for note in self.notes[-5:]:
                lines.append(
                    f"- {note}"
                )

        return "\n".join(
            lines
        )

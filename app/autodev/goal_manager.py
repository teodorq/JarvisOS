from __future__ import annotations

from typing import Any

from app.autodev.goal import Goal


class GoalManager:

    def __init__(self) -> None:
        self.goals: list[Goal] = []

    def add_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 5,
        category: str = "development",
    ) -> Goal:

        normalized_title = str(title).strip()

        if not normalized_title:
            raise ValueError("Tytuł celu nie może być pusty.")

        existing = self.find_by_title(normalized_title)

        if existing is not None:
            return existing

        goal = Goal(
            title=normalized_title,
            description=str(description).strip(),
            priority=self._normalize_priority(priority),
            category=str(category).strip() or "development",
        )

        self.goals.append(goal)
        self._sort()

        return goal

    def find_by_title(
        self,
        title: str,
    ) -> Goal | None:

        normalized = str(title).strip().casefold()

        for goal in self.goals:
            if str(goal.title).strip().casefold() == normalized:
                return goal

        return None

    def get_next_goal(self) -> Goal | None:
        self._sort()

        for goal in self.goals:
            if getattr(goal, "status", "") in {
                "new",
                "planning",
            }:
                return goal

        return None

    def start_next(self) -> Goal | None:
        goal = self.get_next_goal()

        if goal is not None:
            goal.start()

        return goal

    def finish_goal(
        self,
        goal: Goal,
    ) -> None:
        goal.complete()
        self._sort()

    def fail_goal(
        self,
        goal: Goal,
    ) -> None:
        goal.fail()
        self._sort()

    def reprioritize(
        self,
        goal: Goal,
        priority: int,
    ) -> Goal:

        goal.priority = self._normalize_priority(priority)
        self._sort()

        return goal

    def pending(self) -> list[Goal]:
        return [
            goal
            for goal in self.goals
            if getattr(goal, "status", "") in {
                "new",
                "planning",
            }
        ]

    def active(self) -> list[Goal]:
        return [
            goal
            for goal in self.goals
            if getattr(goal, "status", "") in {
                "active",
                "running",
                "in_progress",
            }
        ]

    def completed(self) -> list[Goal]:
        return [
            goal
            for goal in self.goals
            if getattr(goal, "status", "") == "completed"
        ]

    def failed(self) -> list[Goal]:
        return [
            goal
            for goal in self.goals
            if getattr(goal, "status", "") == "failed"
        ]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "total": len(self.goals),
            "pending": len(self.pending()),
            "active": len(self.active()),
            "completed": len(self.completed()),
            "failed": len(self.failed()),
            "next_goal": (
                getattr(self.get_next_goal(), "title", None)
            ),
        }

    def summary(self) -> str:
        lines = [
            "GOAL MANAGER",
            "",
        ]

        if not self.goals:
            lines.append("Brak celów.")
            return "\n".join(lines)

        for goal in self.goals:
            lines.append(
                f"[{getattr(goal, 'status', 'unknown')}] "
                f"P{getattr(goal, 'priority', 5)} "
                f"{getattr(goal, 'title', '')}"
            )

        return "\n".join(lines)

    def _sort(self) -> None:
        self.goals.sort(
            key=lambda goal: (
                self._normalize_priority(
                    getattr(goal, "priority", 5)
                ),
                getattr(goal, "created_at", 0),
            )
        )

    def _normalize_priority(
        self,
        priority: int,
    ) -> int:
        try:
            value = int(priority)
        except (TypeError, ValueError):
            value = 5

        return max(1, min(10, value))

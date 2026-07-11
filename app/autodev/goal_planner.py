from __future__ import annotations

from app.autodev.development_plan import DevelopmentPlan
from app.autodev.development_task import DevelopmentTask
from app.autodev.goal import Goal


class GoalPlanner:

    def build_plan(
        self,
        goal: Goal,
    ) -> DevelopmentPlan:

        plan = DevelopmentPlan(
            goal=goal.title
        )

        steps = self._build_steps(goal)

        for step in steps:
            plan.add_task(
                DevelopmentTask(
                    title=step["title"],
                    description=step["description"],
                    priority=step["priority"],
                    estimated_minutes=step["estimated_minutes"],
                )
            )

        return plan

    def _build_steps(
        self,
        goal: Goal,
    ) -> list[dict]:

        category = str(
            getattr(goal, "category", "development")
        ).casefold()

        steps = [
            {
                "title": "Analiza celu",
                "description": (
                    "Zweryfikuj cel, zakres oraz oczekiwany wynik."
                ),
                "priority": 1,
                "estimated_minutes": 3,
            },
            {
                "title": "Analiza projektu",
                "description": (
                    "Znajdź moduły związane z celem."
                ),
                "priority": 2,
                "estimated_minutes": 5,
            },
            {
                "title": "Analiza zależności",
                "description": (
                    "Sprawdź wpływ zmian na pozostałe moduły."
                ),
                "priority": 3,
                "estimated_minutes": 5,
            },
            {
                "title": "Plan bezpiecznej zmiany",
                "description": (
                    "Określ pliki, rollback i kryteria sukcesu."
                ),
                "priority": 4,
                "estimated_minutes": 5,
            },
            {
                "title": "Generowanie patcha",
                "description": (
                    "Przygotuj ChangeTransaction."
                ),
                "priority": 5,
                "estimated_minutes": 10,
            },
            {
                "title": "Preview zmian",
                "description": "Wygeneruj Diff.",
                "priority": 6,
                "estimated_minutes": 2,
            },
            {
                "title": "Walidacja",
                "description": (
                    "Uruchom syntax, compile, import oraz testy."
                ),
                "priority": 7,
                "estimated_minutes": 8,
            },
            {
                "title": "Finalny raport",
                "description": (
                    "Podsumuj wynik, błędy i wnioski."
                ),
                "priority": 8,
                "estimated_minutes": 2,
            },
        ]

        if category in {
            "bug",
            "repair",
            "fix",
        }:
            steps.insert(
                3,
                {
                    "title": "Odtworzenie problemu",
                    "description": (
                        "Potwierdź błąd przed przygotowaniem poprawki."
                    ),
                    "priority": 4,
                    "estimated_minutes": 5,
                },
            )

        return steps

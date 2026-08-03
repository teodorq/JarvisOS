from __future__ import annotations

import re
from dataclasses import replace

from .dependency_planner import DependencyPlanner
from .models import (
    ImplementationPlan,
    ImplementationTask,
)
from .parallel_execution_planner import (
    ParallelExecutionPlanner,
)


class TaskDecompositionEngine:

    def __init__(self) -> None:
        self.dependencies = DependencyPlanner()
        self.parallel = ParallelExecutionPlanner()

    def decompose(
        self,
        objective: str,
    ) -> ImplementationPlan:
        normalized = " ".join(
            str(objective).split()
        ).strip()

        if not normalized:
            raise ValueError(
                "Objective cannot be empty"
            )

        slug = self._slug(normalized)
        tasks = self._build_tasks(
            objective=normalized,
            slug=slug,
        )

        self.dependencies.validate(tasks)
        execution_order = (
            self.dependencies.topological_order(
                tasks
            )
        )
        parallel_groups = (
            self.parallel.build_groups(tasks)
        )

        total_minutes = sum(
            task.estimated_minutes
            for task in tasks
        )
        average_roi = round(
            sum(task.estimated_roi for task in tasks)
            / len(tasks),
            3,
        )
        average_risk = round(
            sum(task.estimated_risk for task in tasks)
            / len(tasks),
            3,
        )

        return ImplementationPlan(
            objective=normalized,
            tasks=tasks,
            execution_order=execution_order,
            parallel_groups=parallel_groups,
            total_estimated_minutes=total_minutes,
            average_roi=average_roi,
            average_risk=average_risk,
        )

    def _build_tasks(
        self,
        objective: str,
        slug: str,
    ) -> list[ImplementationTask]:
        specifications = [
            {
                "key": "requirements",
                "title": "Analiza wymagań",
                "description": (
                    f"Zdefiniuj zakres i kryteria "
                    f"akceptacji dla: {objective}"
                ),
                "category": "analysis",
                "priority": "high",
                "minutes": 20,
                "roi": 0.86,
                "risk": 0.12,
                "dependencies": [],
                "criteria": [
                    "Zakres funkcji jest jednoznaczny.",
                    "Kryteria akceptacji są mierzalne.",
                ],
            },
            {
                "key": "impact",
                "title": "Analiza wpływu na projekt",
                "description": (
                    "Sprawdź zależności, integracje "
                    "i potencjalne regresje."
                ),
                "category": "analysis",
                "priority": "high",
                "minutes": 25,
                "roi": 0.82,
                "risk": 0.18,
                "dependencies": ["requirements"],
                "criteria": [
                    "Lista zależności jest kompletna.",
                    "Ryzyka regresji są opisane.",
                ],
            },
            {
                "key": "architecture",
                "title": "Projekt rozwiązania",
                "description": (
                    "Przygotuj strukturę modułów, "
                    "interfejsów i przepływu danych."
                ),
                "category": "architecture",
                "priority": "high",
                "minutes": 30,
                "roi": 0.90,
                "risk": 0.22,
                "dependencies": ["requirements"],
                "criteria": [
                    "Architektura jest zgodna z projektem.",
                    "Granice modułów są jasno określone.",
                ],
            },
            {
                "key": "tests",
                "title": "Projekt testów",
                "description": (
                    "Zaprojektuj testy jednostkowe "
                    "i integracyjne przed implementacją."
                ),
                "category": "qa",
                "priority": "high",
                "minutes": 25,
                "roi": 0.88,
                "risk": 0.15,
                "dependencies": [
                    "requirements",
                    "architecture",
                ],
                "criteria": [
                    "Testy pokrywają kryteria akceptacji.",
                    "Uwzględniono scenariusze błędne.",
                ],
            },
            {
                "key": "implementation",
                "title": "Implementacja funkcjonalności",
                "description": (
                    f"Zaimplementuj funkcjonalność: "
                    f"{objective}"
                ),
                "category": "implementation",
                "priority": "high",
                "minutes": 90,
                "roi": 0.95,
                "risk": 0.48,
                "dependencies": [
                    "impact",
                    "architecture",
                    "tests",
                ],
                "criteria": [
                    "Kod spełnia kryteria akceptacji.",
                    "Publiczne interfejsy są stabilne.",
                ],
            },
            {
                "key": "integration",
                "title": "Integracja z JARVIS OS",
                "description": (
                    "Połącz nową funkcjonalność "
                    "z istniejącym pipeline'em."
                ),
                "category": "integration",
                "priority": "normal",
                "minutes": 35,
                "roi": 0.84,
                "risk": 0.42,
                "dependencies": ["implementation"],
                "criteria": [
                    "Integracja nie omija zabezpieczeń.",
                    "Istniejące funkcje nadal działają.",
                ],
            },
            {
                "key": "validation",
                "title": "Walidacja i poprawki",
                "description": (
                    "Uruchom testy, popraw błędy "
                    "i zweryfikuj brak regresji."
                ),
                "category": "validation",
                "priority": "high",
                "minutes": 45,
                "roi": 0.92,
                "risk": 0.25,
                "dependencies": [
                    "implementation",
                    "integration",
                ],
                "criteria": [
                    "Wszystkie testy przechodzą.",
                    "Brak nowych regresji.",
                ],
            },
            {
                "key": "documentation",
                "title": "Dokumentacja zmiany",
                "description": (
                    "Zapisz sposób użycia, ograniczenia "
                    "i decyzje techniczne."
                ),
                "category": "documentation",
                "priority": "normal",
                "minutes": 20,
                "roi": 0.62,
                "risk": 0.08,
                "dependencies": [
                    "implementation",
                ],
                "criteria": [
                    "Dokumentacja opisuje konfigurację.",
                    "Znane ograniczenia są zapisane.",
                ],
            },
            {
                "key": "release",
                "title": "Finalizacja wdrożenia",
                "description": (
                    "Przygotuj raport końcowy "
                    "i oznacz funkcjonalność jako gotową."
                ),
                "category": "release",
                "priority": "normal",
                "minutes": 15,
                "roi": 0.68,
                "risk": 0.10,
                "dependencies": [
                    "validation",
                    "documentation",
                ],
                "criteria": [
                    "Raport końcowy jest zapisany.",
                    "Status wdrożenia jest jednoznaczny.",
                ],
            },
        ]

        task_ids = {
            item["key"]: (
                f"{slug}-{index:02d}-"
                f"{item['key']}"
            )
            for index, item
            in enumerate(
                specifications,
                start=1,
            )
        }

        tasks: list[ImplementationTask] = []

        for item in specifications:
            tasks.append(
                ImplementationTask(
                    task_id=task_ids[
                        item["key"]
                    ],
                    title=item["title"],
                    description=item[
                        "description"
                    ],
                    category=item["category"],
                    priority=item["priority"],
                    estimated_minutes=item[
                        "minutes"
                    ],
                    estimated_roi=item["roi"],
                    estimated_risk=item["risk"],
                    dependencies=[
                        task_ids[dependency]
                        for dependency
                        in item["dependencies"]
                    ],
                    acceptance_criteria=list(
                        item["criteria"]
                    ),
                    metadata={
                        "objective": objective,
                        "source": (
                            "task_decomposition_engine"
                        ),
                    },
                )
            )

        return tasks

    @staticmethod
    def _slug(
        value: str,
    ) -> str:
        normalized = re.sub(
            r"[^a-zA-Z0-9]+",
            "-",
            value.lower(),
        ).strip("-")

        if not normalized:
            normalized = "implementation"

        return normalized[:40]

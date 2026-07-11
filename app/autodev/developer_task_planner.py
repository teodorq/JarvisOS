from __future__ import annotations

from app.autodev.developer_task import DeveloperTask


class DeveloperTaskPlanner:

    def create_change_plan(
        self,
        goal: str,
        target: str,
        impacted_files: list,
    ) -> DeveloperTask:

        task = DeveloperTask(
            goal=goal,
            target=target,
        )

        steps = self._steps(
            goal=goal,
            target=target,
            impacted_files=impacted_files,
        )

        for step in steps:
            task.add_step(
                name=step["name"],
                description=step["description"],
                action_type=step["action_type"],
                target=target,
            )

        return task

    def _steps(
        self,
        *,
        goal: str,
        target: str,
        impacted_files: list,
    ) -> list[dict[str, str]]:

        return [
            {
                "name": "Analiza celu",
                "description": f"Przeanalizować cel: {goal}",
                "action_type": "ANALYZE_GOAL",
            },
            {
                "name": "Analiza zależności",
                "description": (
                    f"Sprawdzić wpływ zmiany symbolu: {target}. "
                    f"Znalezionych plików: {len(impacted_files)}"
                ),
                "action_type": "ANALYZE_DEPENDENCIES",
            },
            {
                "name": "Ocena ryzyka",
                "description": (
                    "Określić ryzyko zmiany i wymagany poziom kontroli."
                ),
                "action_type": "ASSESS_RISK",
            },
            {
                "name": "Backup",
                "description": (
                    "Utworzyć backup plików przed zmianą."
                ),
                "action_type": "BACKUP_FILES",
            },
            {
                "name": "Przygotowanie poprawki",
                "description": (
                    "Przygotować bezpieczny szkic zmian."
                ),
                "action_type": "BUILD_PATCH",
            },
            {
                "name": "Walidacja składni",
                "description": (
                    "Sprawdzić składnię zmienianych plików."
                ),
                "action_type": "CHECK_SYNTAX",
            },
            {
                "name": "Test importów",
                "description": (
                    "Uruchomić test importów projektu."
                ),
                "action_type": "RUN_IMPORT_TEST",
            },
            {
                "name": "Testy projektu",
                "description": (
                    "Uruchomić testy regresyjne projektu."
                ),
                "action_type": "RUN_TESTS",
            },
            {
                "name": "Raport",
                "description": (
                    "Przygotować raport z planowanych zmian."
                ),
                "action_type": "BUILD_REPORT",
            },
        ]

from __future__ import annotations

from typing import Any

from app.autodev.change_impact import ChangeImpactAnalyzer
from app.autodev.developer_report import DeveloperReport
from app.autodev.developer_task_planner import DeveloperTaskPlanner


class DeveloperLoop:

    def __init__(self) -> None:
        self.impact = ChangeImpactAnalyzer()
        self.planner = DeveloperTaskPlanner()
        self.report_builder = DeveloperReport()
        self.history: list[dict[str, Any]] = []

    def prepare(
        self,
        goal_text: str,
        target: str,
    ) -> str:

        normalized_goal = str(goal_text).strip()
        normalized_target = str(target).strip()

        if not normalized_goal:
            raise ValueError(
                "Cel DeveloperLoop nie może być pusty."
            )

        if not normalized_target:
            raise ValueError(
                "Target DeveloperLoop nie może być pusty."
            )

        self.impact.build_graph()

        impact_data = self.impact.graph.impact_for_symbol(
            normalized_target
        )

        impacted_files = impact_data.get(
            "files",
            [],
        )

        task = self.planner.create_change_plan(
            goal=normalized_goal,
            target=normalized_target,
            impacted_files=impacted_files,
        )

        notes: list[str] = []
        lessons: list[str] = []

        while not task.finished:
            step = task.get_current_step()

            if step is None:
                break

            step.start()

            try:
                result = self._execute_dry_run_step(
                    step.action_type,
                    normalized_target,
                    impacted_files,
                )

                task.complete_current_step(
                    result
                )

                notes.append(
                    f"{step.name}: {result}"
                )

            except Exception as error:
                task.fail_current_step(
                    str(error)
                )

                lessons.append(
                    f"Błąd w kroku {step.name}: {error}"
                )

                break

        success = not task.failed

        if success:
            lessons.append(
                "Plan został przygotowany bez błędów."
            )

        record = {
            "goal": normalized_goal,
            "target": normalized_target,
            "success": success,
            "impacted_files": list(
                impacted_files
            ),
            "notes": list(
                notes
            ),
            "lessons": list(
                lessons
            ),
        }

        self.history.append(
            record
        )

        return self.report_builder.build(
            goal=normalized_goal,
            target=normalized_target,
            impacted_files=impacted_files,
            task_summary=task.summary(),
            success=success,
            notes=notes,
            lessons=lessons,
            metadata={
                "history_count": len(
                    self.history
                ),
                "mode": "planning",
            },
        )

    def last_run(
        self,
    ) -> dict[str, Any] | None:

        if not self.history:
            return None

        return dict(
            self.history[-1]
        )

    def _execute_dry_run_step(
        self,
        action_type: str,
        target: str,
        impacted_files: list,
    ) -> str:

        if action_type == "ANALYZE_GOAL":
            return (
                f"Cel został przyjęty dla symbolu: {target}"
            )

        if action_type == "ANALYZE_DEPENDENCIES":
            return (
                f"Znaleziono {len(impacted_files)} "
                "plików zależnych."
            )

        if action_type == "ASSESS_RISK":
            risk = (
                "HIGH"
                if len(impacted_files) > 10
                else "NORMAL"
            )

            return f"Poziom ryzyka: {risk}."

        if action_type == "BACKUP_FILES":
            return (
                "TRYB PLANOWANIA: backup nie został wykonany."
            )

        if action_type == "BUILD_PATCH":
            return (
                "TRYB PLANOWANIA: patch nie został zapisany."
            )

        if action_type == "CHECK_SYNTAX":
            return (
                "TRYB PLANOWANIA: test składni zostanie "
                "wykonany po utworzeniu patcha."
            )

        if action_type == "RUN_IMPORT_TEST":
            return (
                "TRYB PLANOWANIA: test importów zostanie "
                "wykonany po zaakceptowaniu zmian."
            )

        if action_type == "RUN_TESTS":
            return (
                "TRYB PLANOWANIA: testy projektu zostaną "
                "wykonane po zaakceptowaniu zmian."
            )

        if action_type == "BUILD_REPORT":
            return (
                "Raport planu został przygotowany."
            )

        return f"Nieznany krok: {action_type}"

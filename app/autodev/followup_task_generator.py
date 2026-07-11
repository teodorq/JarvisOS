from __future__ import annotations

from typing import Any


class FollowupTaskGenerator:
    """
    Builds safe follow-up development goals from the result
    of an autonomous task.
    """

    FAILURE_STATUSES = {
        "FAILED",
        "FAILURE",
        "PLANNING_FAILED",
        "CODE_INPUT_REQUIRED",
        "FAILED_AND_ROLLED_BACK",
        "ROLLBACK_FAILED",
    }

    def generate(
        self,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = dict(result or {})
        status = str(
            result.get(
                "status",
                "UNKNOWN",
            )
        ).upper()

        selected_task = result.get(
            "selected_task",
            {},
        )

        if not isinstance(
            selected_task,
            dict,
        ):
            selected_task = {}

        target = str(
            selected_task.get(
                "target",
                "",
            )
        ).strip()

        title = str(
            selected_task.get(
                "title",
                selected_task.get(
                    "description",
                    "",
                ),
            )
        ).strip()

        tasks: list[dict[str, Any]] = []

        if status in self.FAILURE_STATUSES:
            tasks.append(
                {
                    "goal": (
                        "Przeanalizuj przyczynę niepowodzenia "
                        f"zadania: {title or 'nieznane zadanie'}."
                    ),
                    "priority": "HIGH",
                    "target": target,
                    "tags": [
                        "autonomous-dev",
                        "followup",
                        "failure-analysis",
                    ],
                }
            )

            tasks.append(
                {
                    "goal": (
                        "Przygotuj bezpieczną poprawkę po błędzie "
                        f"zadania: {title or 'nieznane zadanie'}."
                    ),
                    "priority": "HIGH",
                    "target": target,
                    "tags": [
                        "autonomous-dev",
                        "followup",
                        "recovery",
                    ],
                }
            )

            return tasks

        if status in {
            "COMPLETED",
            "STOPPED",
            "SUCCESS",
        }:
            tasks.append(
                {
                    "goal": (
                        "Zweryfikuj skutki ostatniej udanej zmiany"
                        + (
                            f" dla: {title}."
                            if title
                            else "."
                        )
                    ),
                    "priority": "NORMAL",
                    "target": target,
                    "tags": [
                        "autonomous-dev",
                        "followup",
                        "verification",
                    ],
                }
            )

        return tasks

from __future__ import annotations

from typing import Any


class AutoDevStepValidator:
    def validate(
        self,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        errors: list[str] = []

        step_id = str(
            step.get(
                "step_id",
                "",
            )
        ).strip()

        title = str(
            step.get(
                "title",
                "",
            )
        ).strip()

        if not step_id:
            errors.append("Brak step_id.")

        if not title:
            errors.append("Brak tytułu kroku.")

        return {
            "success": not errors,
            "status": (
                "STEP_VALID"
                if not errors
                else "STEP_INVALID"
            ),
            "step_id": step_id,
            "errors": errors,
        }

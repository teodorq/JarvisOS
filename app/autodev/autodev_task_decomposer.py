from __future__ import annotations

from typing import Any


class AutoDevTaskDecomposer:
    DEFAULT_STEPS = (
        "Przeanalizuj cel i kontekst.",
        "Zidentyfikuj pliki oraz zależności.",
        "Przygotuj plan zmiany.",
        "Wykonaj symulację wpływu.",
        "Zweryfikuj bezpieczeństwo.",
        "Przygotuj preview.",
        "Wygeneruj raport.",
    )

    def decompose(
        self,
        goal: str,
    ) -> dict[str, Any]:
        normalized = str(goal).strip()

        if not normalized:
            return {
                "success": False,
                "status": "EMPTY_GOAL",
                "steps": [],
            }

        steps = [
            {
                "step_id": f"step-{index}",
                "order": index,
                "title": title,
                "goal": normalized,
                "status": "PENDING",
            }
            for index, title in enumerate(
                self.DEFAULT_STEPS,
                start=1,
            )
        ]

        return {
            "success": True,
            "status": "TASK_DECOMPOSED",
            "goal": normalized,
            "steps": steps,
        }

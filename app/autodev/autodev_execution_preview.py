from __future__ import annotations

from typing import Any


class AutoDevExecutionPreview:
    def build(
        self,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        steps = list(
            (
                plan.get(
                    "decomposition",
                    {},
                )
                or {}
            ).get(
                "steps",
                [],
            )
        )

        summary_lines = [
            "AUTODEV MULTI-STAGE PREVIEW",
            f"Cel: {plan.get('goal', '')}",
            f"Liczba kroków: {len(steps)}",
        ]

        for step in steps:
            summary_lines.append(
                (
                    f"{step.get('order', '?')}. "
                    f"{step.get('title', '')}"
                )
            )

        return {
            "success": bool(
                plan.get(
                    "success",
                    False,
                )
            ),
            "status": "EXECUTION_PREVIEW_READY",
            "summary": "\n".join(summary_lines),
            "steps": steps,
            "approved": False,
            "writes_code": False,
        }

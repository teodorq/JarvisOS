from __future__ import annotations

from typing import Any

from app.autodev.learning_engine import LearningEngine
from app.autodev.reasoning_memory import ReasoningMemory


class LearningBridge:
    """
    Sends one autonomous result to both experience memory
    and reasoning memory.
    """

    def __init__(
        self,
        *,
        learning_engine: LearningEngine | None = None,
        reasoning_memory: ReasoningMemory | None = None,
    ) -> None:
        self.learning_engine = (
            learning_engine or LearningEngine()
        )
        self.reasoning_memory = (
            reasoning_memory or ReasoningMemory()
        )

    def record(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(result or {})

        learning = self.learning_engine.learn_from_result(
            normalized
        )

        reasoning_record = {
            "success": bool(
                normalized.get(
                    "success",
                    False,
                )
            ),
            "status": str(
                normalized.get(
                    "status",
                    "UNKNOWN",
                )
            ),
            "goal": self._goal_from_result(
                normalized
            ),
            "lessons": self._lessons_from_result(
                normalized
            ),
            "errors": self._errors_from_result(
                normalized
            ),
        }

        self.reasoning_memory.remember(
            reasoning_record
        )

        return {
            "success": True,
            "status": "RECORDED",
            "learning": learning,
            "reasoning": (
                self.reasoning_memory.summary_dict()
            ),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "experience": self.learning_engine.summary(),
            "reasoning": self.reasoning_memory.summary_dict(),
        }

    def _goal_from_result(
        self,
        result: dict[str, Any],
    ) -> str:
        selected = result.get(
            "selected_task",
            {},
        )

        if isinstance(
            selected,
            dict,
        ):
            return str(
                selected.get(
                    "description",
                    selected.get(
                        "title",
                        "",
                    ),
                )
            )

        return ""

    def _lessons_from_result(
        self,
        result: dict[str, Any],
    ) -> list[str]:
        lessons: list[str] = []

        stop_reason = result.get(
            "stop_reason"
        )

        if stop_reason:
            lessons.append(
                f"Powód zatrzymania: {stop_reason}"
            )

        status = result.get(
            "status"
        )

        if status:
            lessons.append(
                f"Status końcowy: {status}"
            )

        return lessons

    def _errors_from_result(
        self,
        result: dict[str, Any],
    ) -> list[str]:
        errors = result.get(
            "errors",
            [],
        )

        if isinstance(
            errors,
            list,
        ):
            return [
                str(error)
                for error in errors
            ]

        error = result.get(
            "error"
        )

        return [str(error)] if error else []

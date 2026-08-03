from __future__ import annotations

from typing import Any, Iterable

from app.ai.evolution.autonomous_evolution_engine import (
    AutonomousEvolutionEngine,
)


class EvolutionBacklogSelector:
    """Adapter wybierający najlepsze PENDING zadanie z backlogu."""

    def __init__(
        self,
        engine: AutonomousEvolutionEngine | None = None,
    ) -> None:
        self.engine = engine or AutonomousEvolutionEngine()

    def select(
        self,
        items: Iterable[Any],
    ) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []

        for item in items:
            task = self._to_dict(item)
            if str(task.get("status", "PENDING")).upper() != "PENDING":
                continue
            candidates.append(task)

        return self.engine.select_best_task(candidates)

    @staticmethod
    def _to_dict(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return dict(item)
        to_dict = getattr(item, "to_dict", None)
        if callable(to_dict):
            result = to_dict()
            return dict(result) if isinstance(result, dict) else {}
        return {}

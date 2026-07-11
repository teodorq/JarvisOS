from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class DeveloperStrategy:
    name: str
    priority: int
    issue_types: tuple[str, ...]
    requires_llm: bool = False
    requires_approval: bool = True
    safe_execution: bool = True
    auto_rollback: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeveloperStrategyManager:
    """
    Dobiera strategię wykonania na podstawie typu problemu.

    Moduł nie zapisuje plików i nie uruchamia zmian.
    """

    def __init__(
        self,
    ) -> None:

        self.strategies = (
            DeveloperStrategy(
                name="local_safe_refactor",
                priority=100,
                issue_types=(
                    "EMPTY_BLOCK",
                    "TODO",
                    "BROAD_EXCEPTION",
                ),
                requires_llm=False,
            ),
            DeveloperStrategy(
                name="llm_guided_refactor",
                priority=80,
                issue_types=(
                    "LONG_FUNCTION",
                    "LARGE_CLASS",
                    "TOO_MANY_ARGUMENTS",
                ),
                requires_llm=True,
            ),
            DeveloperStrategy(
                name="analysis_only",
                priority=10,
                issue_types=(),
                requires_llm=False,
                metadata={
                    "fallback": True,
                },
            ),
        )

        self.last_selection: dict[str, Any] | None = None

    def select(
        self,
        *,
        issue_type: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized = str(
            issue_type
        ).strip().upper()

        context = dict(
            context or {}
        )

        matching = [
            strategy
            for strategy in self.strategies
            if normalized in strategy.issue_types
        ]

        if not matching:
            selected = self.strategies[-1]
        else:
            selected = sorted(
                matching,
                key=lambda item: -item.priority,
            )[0]

        result = selected.to_dict()

        result["issue_type"] = normalized
        result["context"] = context

        self.last_selection = dict(
            result
        )

        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "strategies": [
                strategy.to_dict()
                for strategy in self.strategies
            ],
            "last_selection": self.last_selection,
        }

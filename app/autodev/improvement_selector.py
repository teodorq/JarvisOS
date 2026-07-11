from __future__ import annotations

from typing import Any


class ImprovementSelector:

    DEFAULT_PRIORITY = [
        "brain",
        "autodev",
        "reasoning",
        "memory",
        "vision",
        "planner",
        "ui",
    ]

    def __init__(self) -> None:

        self.last_selection: dict[str, Any] | None = None

    def select(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:

        if not tasks:
            return None

        def score(
            task: dict[str, Any],
        ) -> int:

            title = str(
                task.get(
                    "title",
                    "",
                )
            ).lower()

            for index, keyword in enumerate(
                self.DEFAULT_PRIORITY
            ):
                if keyword in title:
                    return index

            return len(
                self.DEFAULT_PRIORITY
            )

        selected = sorted(
            tasks,
            key=score,
        )[0]

        self.last_selection = dict(
            selected
        )

        return selected

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_selection": self.last_selection,
        }
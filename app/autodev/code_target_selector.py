from __future__ import annotations

from pathlib import Path
from typing import Any


class CodeTargetSelector:

    def __init__(self) -> None:

        self.last_selection: dict[str, Any] | None = None

    def select(
        self,
        analysis: dict[str, Any],
    ) -> dict[str, Any] | None:

        files = analysis.get(
            "files",
            [],
        )

        if not isinstance(
            files,
            list,
        ):
            return None

        candidates: list[
            dict[str, Any]
        ] = []

        for path_value in files:
            file_path = Path(
                str(path_value)
            )

            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(
                    encoding="utf-8"
                )
            except Exception:
                continue

            lines_count = len(
                content.splitlines()
            )

            score = self._calculate_score(
                path=file_path,
                content=content,
                lines_count=lines_count,
            )

            candidates.append(
                {
                    "path": str(
                        file_path
                    ),
                    "name": file_path.name,
                    "lines_count": lines_count,
                    "score": score,
                }
            )

        if not candidates:
            return None

        selected = sorted(
            candidates,
            key=lambda item: (
                -int(
                    item.get(
                        "score",
                        0,
                    )
                ),
                str(
                    item.get(
                        "path",
                        "",
                    )
                ),
            ),
        )[0]

        self.last_selection = dict(
            selected
        )

        return selected

    def _calculate_score(
        self,
        *,
        path: Path,
        content: str,
        lines_count: int,
    ) -> int:

        score = 0

        name = path.name.casefold()
        lowered = content.casefold()

        important_names = (
            "brain.py",
            "controller.py",
            "service.py",
            "engine.py",
            "planner.py",
            "pipeline.py",
        )

        if any(
            keyword in name
            for keyword in important_names
        ):
            score += 30

        if lines_count > 100:
            score += 10

        if lines_count > 300:
            score += 10

        if "todo" in lowered:
            score += 20

        if "pass" in lowered:
            score += 10

        if "except exception" in lowered:
            score += 5

        if "magicmock" in lowered:
            score -= 20

        if path.name.startswith(
            "test_"
        ):
            score -= 50

        if "__init__.py" == path.name:
            score -= 30

        return score

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_selection": (
                self.last_selection
            ),
        }
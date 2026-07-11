from __future__ import annotations

from collections import Counter
from typing import Any

from app.autodev.project_file import ProjectFile


class ProjectDeadCodeDetector:
    """
    Wskazuje funkcje i klasy występujące tylko raz w indeksie nazw.

    To heurystyka do review, nie dowód martwego kodu.
    """

    IGNORED_NAMES = {
        "__init__",
        "__main__",
        "main",
        "run",
        "status",
        "handle",
    }

    def detect(
        self,
        project_files: list[ProjectFile],
    ) -> dict[str, Any]:
        names: Counter[str] = Counter()

        for item in project_files:
            names.update(item.functions)
            names.update(item.classes)

        candidates: list[dict[str, Any]] = []

        for item in project_files:
            for kind, values in (
                ("function", item.functions),
                ("class", item.classes),
            ):
                for name in values:
                    if (
                        name in self.IGNORED_NAMES
                        or name.startswith("test_")
                        or name.startswith("__")
                        or names[name] != 1
                    ):
                        continue

                    candidates.append(
                        {
                            "path": item.path,
                            "kind": kind,
                            "name": name,
                            "confidence": "LOW",
                            "reason": (
                                "Nazwa występuje tylko raz "
                                "w indeksie projektu."
                            ),
                        }
                    )

        return {
            "success": True,
            "status": "DEAD_CODE_CANDIDATES_READY",
            "candidates": candidates,
            "count": len(candidates),
            "heuristic_only": True,
            "writes_code": False,
        }

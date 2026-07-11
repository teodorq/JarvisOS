from __future__ import annotations

import ast
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any


class ProjectDuplicateDetector:
    """
    Wykrywa identyczne ciała funkcji na podstawie AST.
    Nie wykonuje kodu i nie modyfikuje projektu.
    """

    def detect(
        self,
        paths: list[str],
    ) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        errors: list[str] = []

        for raw_path in paths:
            path = Path(raw_path)

            try:
                source = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                tree = ast.parse(source)
            except (OSError, SyntaxError) as error:
                errors.append(
                    f"{path}: {type(error).__name__}: {error}"
                )
                continue

            for node in ast.walk(tree):
                if not isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    continue

                normalized = ast.dump(
                    ast.Module(
                        body=node.body,
                        type_ignores=[],
                    ),
                    include_attributes=False,
                )

                digest = hashlib.sha256(
                    normalized.encode("utf-8")
                ).hexdigest()

                groups[digest].append(
                    {
                        "path": str(path),
                        "function": node.name,
                        "line": int(
                            getattr(node, "lineno", 0)
                        ),
                    }
                )

        duplicates = [
            items
            for items in groups.values()
            if len(items) > 1
        ]

        duplicates.sort(
            key=len,
            reverse=True,
        )

        return {
            "success": True,
            "status": "DUPLICATES_ANALYZED",
            "duplicate_groups": duplicates,
            "duplicate_groups_count": len(duplicates),
            "errors": errors,
            "writes_code": False,
        }

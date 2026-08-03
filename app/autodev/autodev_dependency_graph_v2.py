from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import ast
from pathlib import Path
from typing import Any


class AutoDevDependencyGraphV2:
    """
    Buduje prosty graf importów na podstawie AST.
    """

    def __init__(
        self,
        project_root: str = default_project_root(),
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.graph: dict[str, list[str]] = {}
        self.errors: list[str] = []

    def build(self) -> dict[str, Any]:
        self.graph = {}
        self.errors = []

        for path in self.project_root.rglob("*.py"):
            try:
                source = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                tree = ast.parse(source)
            except (OSError, SyntaxError) as error:
                self.errors.append(
                    f"{path}: {type(error).__name__}: {error}"
                )
                continue

            imports: set[str] = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)

            self.graph[str(path)] = sorted(imports)

        return {
            "success": True,
            "status": "DEPENDENCY_GRAPH_READY",
            "nodes": len(self.graph),
            "graph": dict(self.graph),
            "errors": list(self.errors),
            "writes_code": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "nodes": len(self.graph),
            "errors": list(self.errors),
        }

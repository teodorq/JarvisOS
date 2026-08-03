from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class CodeMapBuilder:
    def build(self, project_root: str | Path) -> dict[str, dict[str, Any]]:
        root = Path(project_root).resolve()
        result: dict[str, dict[str, Any]] = {}

        for path in self._python_files(root):
            relative = path.relative_to(root).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, UnicodeDecodeError, SyntaxError) as exc:
                result[relative] = {
                    "parse_error": str(exc),
                    "classes": [],
                    "functions": [],
                    "imports": [],
                    "line_count": 0,
                }
                continue

            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            functions = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            imports = self._imports(tree)
            result[relative] = {
                "classes": sorted(set(classes)),
                "functions": sorted(set(functions)),
                "imports": sorted(set(imports)),
                "line_count": len(source.splitlines()),
            }

        return result

    @staticmethod
    def _imports(tree: ast.AST) -> list[str]:
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return imports

    @staticmethod
    def _python_files(root: Path):
        ignored = {".git", ".venv", "venv", "__pycache__", "AI_PLIKI", "node_modules"}
        for path in root.rglob("*.py"):
            if not any(part in ignored for part in path.parts):
                yield path

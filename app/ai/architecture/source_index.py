from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceFile:
    path: Path
    module: str
    source: str
    tree: ast.AST
    line_count: int


class SourceIndex:

    def __init__(
        self,
        project_root: str | Path,
        source_root: str = "app",
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.source_root = source_root

    def build(self) -> list[SourceFile]:
        source_path = self.project_root / self.source_root
        if not source_path.exists():
            return []

        indexed: list[SourceFile] = []

        for path in sorted(source_path.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue

            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue

            indexed.append(
                SourceFile(
                    path=path,
                    module=self._module_name(path),
                    source=source,
                    tree=tree,
                    line_count=len(source.splitlines()),
                )
            )

        return indexed

    def _module_name(self, path: Path) -> str:
        relative = path.relative_to(self.project_root)
        parts = list(relative.with_suffix("").parts)

        if parts and parts[-1] == "__init__":
            parts.pop()

        return ".".join(parts)

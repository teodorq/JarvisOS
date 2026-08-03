from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import ast
from pathlib import Path

from app.autodev.file_classifier import FileClassifier
from app.autodev.project_file import ProjectFile
from app.autodev.project_index import ProjectIndex


class ProjectScanner:

    DEFAULT_IGNORED_DIRS = {
        ".git",
        ".idea",
        ".pytest_cache",
        ".venv",
        "archive",
        "backups",
        "build",
        "dist",
        "__pycache__",
    }

    def __init__(
        self,
        project_root: str = default_project_root(),
        ignored_dirs: set[str] | None = None,
    ) -> None:

        self.project_root = Path(
            project_root
        ).resolve()

        self.classifier = FileClassifier()

        self.ignored_dirs = set(
            ignored_dirs
            or self.DEFAULT_IGNORED_DIRS
        )

        self.errors: list[dict[str, str]] = []

    def scan(self) -> ProjectIndex:
        index = ProjectIndex()
        self.errors = []

        for file_path in self._iter_python_files():
            project_file = self._scan_file(
                file_path
            )

            if project_file is not None:
                index.add(
                    project_file
                )

        return index

    def scan_with_report(self) -> dict:
        index = self.scan()

        return {
            "success": True,
            "project_root": str(
                self.project_root
            ),
            "files_count": index.count(),
            "errors_count": len(
                self.errors
            ),
            "errors": list(
                self.errors
            ),
            "index": index,
        }

    def _iter_python_files(self):
        for file_path in self.project_root.rglob(
            "*.py"
        ):
            relative_parts = set(
                file_path.relative_to(
                    self.project_root
                ).parts
            )

            if relative_parts.intersection(
                self.ignored_dirs
            ):
                continue

            yield file_path

    def _scan_file(
        self,
        file_path: Path,
    ) -> ProjectFile | None:

        try:
            source = file_path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                source
            )

        except Exception as error:
            self.errors.append(
                {
                    "path": str(
                        file_path
                    ),
                    "error": (
                        f"{type(error).__name__}: "
                        f"{error}"
                    ),
                }
            )

            return None

        project_file = ProjectFile(
            path=str(
                file_path
            ),
            category=self.classifier.classify(
                str(
                    file_path
                )
            ),
            size=len(
                source.encode(
                    "utf-8"
                )
            ),
        )

        project_file.line_count = len(
            source.splitlines()
        )

        for node in ast.walk(
            tree
        ):
            if isinstance(
                node,
                ast.Import,
            ):
                for alias in node.names:
                    project_file.imports.append(
                        alias.name
                    )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):
                project_file.imports.append(
                    node.module
                    or ""
                )

            elif isinstance(
                node,
                ast.ClassDef,
            ):
                project_file.classes.append(
                    node.name
                )

            elif isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                project_file.functions.append(
                    node.name
                )

        return project_file

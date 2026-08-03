from __future__ import annotations

import ast
import hashlib
from pathlib import Path, PurePosixPath
from typing import Iterable

from app.autodev.reference_finder import ReferenceFinder


class RefactorSourceIndex:
    """Read-only index of Python modules, imports and symbol references."""

    EXCLUDED_PARTS = {
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "AI_PLIKI",
        "__pycache__",
        "archive",
        "data",
        "venv",
    }

    def __init__(
        self,
        project_root: str | Path,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.reference_finder = (
            ReferenceFinder()
        )

    def project_python_files(
        self,
    ) -> list[Path]:
        files: list[Path] = []

        for path in self.project_root.rglob(
            "*.py"
        ):
            try:
                relative = path.relative_to(
                    self.project_root
                )
            except ValueError:
                continue

            if any(
                part in self.EXCLUDED_PARTS
                or part.casefold().endswith(
                    ".egg-info"
                )
                for part in relative.parts
            ):
                continue

            if (
                path.is_file()
                and not path.is_symlink()
            ):
                files.append(
                    path.resolve(
                        strict=False
                    )
                )

        return sorted(
            set(files),
            key=self.relative_path,
        )

    def module_graph(
        self,
        project_files: Iterable[Path],
        *,
        replacements: dict[str, str] | None = None,
    ) -> dict[str, set[str]]:
        files = list(
            project_files
        )
        replacements = {
            str(
                Path(path).resolve(
                    strict=False
                )
            ): content
            for path, content in dict(
                replacements or {}
            ).items()
        }
        module_names = {
            self.module_name(
                self.relative_path(path)
            )
            for path in files
        }
        graph: dict[str, set[str]] = {
            module: set()
            for module in module_names
        }

        for path in files:
            relative = self.relative_path(
                path
            )
            source_module = self.module_name(
                relative
            )
            content = replacements.get(
                str(path)
            )

            if content is None:
                try:
                    content = path.read_text(
                        encoding="utf-8"
                    )
                except (
                    OSError,
                    UnicodeError,
                ):
                    continue

            try:
                tree = ast.parse(
                    content,
                    filename=str(path),
                )
            except SyntaxError:
                continue

            for imported in self.imports(
                tree,
                source_module=source_module,
                source_path=relative,
            ):
                resolved = (
                    self.resolve_imported_module(
                        imported,
                        module_names,
                    )
                )

                if resolved:
                    graph.setdefault(
                        source_module,
                        set(),
                    ).add(
                        resolved
                    )

        return graph

    def reverse_dependents(
        self,
        graph: dict[str, set[str]],
        module_to_relative: dict[str, str],
    ) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}

        for source, targets in graph.items():
            source_path = module_to_relative.get(
                source
            )

            if not source_path:
                continue

            for target in targets:
                result.setdefault(
                    target,
                    set(),
                ).add(
                    source_path
                )

        return result

    def reference_files(
        self,
        project_files: Iterable[Path],
        *,
        symbols: Iterable[str],
        excluded: set[str],
    ) -> list[str]:
        result: set[str] = set()

        for symbol in sorted(
            {
                str(value).strip()
                for value in symbols
                if str(value).strip()
            }
        ):
            for path in project_files:
                relative = self.relative_path(
                    path
                )

                if relative in excluded:
                    continue

                if (
                    self.reference_finder
                    .find_references(
                        str(path),
                        symbol,
                    )
                ):
                    result.add(
                        relative
                    )

        return sorted(
            result
        )

    @classmethod
    def symbols(
        cls,
        tree: ast.AST,
    ) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}

        for node in getattr(
            tree,
            "body",
            [],
        ):
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                result[node.name] = {
                    "signature": cls.signature(
                        node
                    ),
                    "fingerprint": ast.dump(
                        node,
                        include_attributes=False,
                    ),
                }

        return result

    @staticmethod
    def signature(
        node: ast.AST,
    ) -> str:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            returns = (
                ast.unparse(
                    node.returns
                )
                if node.returns is not None
                else ""
            )
            return (
                f"{node.name}("
                f"{ast.unparse(node.args)})"
                f"->{returns}"
            )

        if isinstance(
            node,
            ast.ClassDef,
        ):
            bases = ",".join(
                ast.unparse(base)
                for base in node.bases
            )
            return (
                f"class {node.name}({bases})"
            )

        return ""

    @classmethod
    def imports(
        cls,
        tree: ast.AST,
        *,
        source_module: str,
        source_path: str,
    ) -> list[str]:
        result: set[str] = set()
        package = (
            source_module
            if PurePosixPath(
                source_path
            ).name == "__init__.py"
            else source_module.rpartition(
                "."
            )[0]
        )

        for node in ast.walk(
            tree
        ):
            if isinstance(
                node,
                ast.Import,
            ):
                result.update(
                    alias.name
                    for alias in node.names
                )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):
                module = node.module or ""

                if node.level:
                    parts = [
                        part
                        for part
                        in package.split(
                            "."
                        )
                        if part
                    ]
                    trim = max(
                        0,
                        node.level - 1,
                    )

                    if trim:
                        parts = (
                            parts[:-trim]
                            if trim <= len(parts)
                            else []
                        )

                    prefix = ".".join(
                        parts
                    )
                    module = ".".join(
                        item
                        for item in (
                            prefix,
                            module,
                        )
                        if item
                    )

                if module:
                    result.add(
                        module
                    )

                for alias in node.names:
                    if (
                        alias.name != "*"
                        and module
                    ):
                        result.add(
                            f"{module}.{alias.name}"
                        )

        return sorted(
            result
        )

    @staticmethod
    def resolve_imported_module(
        imported: str,
        known_modules: set[str],
    ) -> str:
        candidate = str(
            imported
        ).strip()

        while candidate:
            if candidate in known_modules:
                return candidate

            if "." not in candidate:
                break

            candidate = candidate.rpartition(
                "."
            )[0]

        return ""

    @staticmethod
    def cycles(
        graph: dict[str, set[str]],
    ) -> set[frozenset[str]]:
        index = 0
        stack: list[str] = []
        on_stack: set[str] = set()
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        result: set[frozenset[str]] = set()

        def visit(
            node: str,
        ) -> None:
            nonlocal index
            indices[node] = index
            lowlinks[node] = index
            index += 1
            stack.append(
                node
            )
            on_stack.add(
                node
            )

            for target in graph.get(
                node,
                set(),
            ):
                if target not in indices:
                    visit(
                        target
                    )
                    lowlinks[node] = min(
                        lowlinks[node],
                        lowlinks[target],
                    )
                elif target in on_stack:
                    lowlinks[node] = min(
                        lowlinks[node],
                        indices[target],
                    )

            if lowlinks[node] != indices[node]:
                return

            component: set[str] = set()

            while stack:
                value = stack.pop()
                on_stack.discard(
                    value
                )
                component.add(
                    value
                )

                if value == node:
                    break

            if (
                len(component) > 1
                or (
                    len(component) == 1
                    and node in graph.get(
                        node,
                        set(),
                    )
                )
            ):
                result.add(
                    frozenset(
                        component
                    )
                )

        for node in sorted(
            graph
        ):
            if node not in indices:
                visit(
                    node
                )

        return result

    def relative_path(
        self,
        path: Path,
    ) -> str:
        return path.resolve(
            strict=False
        ).relative_to(
            self.project_root
        ).as_posix()

    @staticmethod
    def module_name(
        relative_path: str,
    ) -> str:
        path = PurePosixPath(
            str(relative_path).replace(
                "\\",
                "/",
            )
        )
        parts = list(
            path.with_suffix(
                ""
            ).parts
        )

        if (
            parts
            and parts[-1] == "__init__"
        ):
            parts.pop()

        return ".".join(
            parts
        )

    @staticmethod
    def hash_text(
        value: str,
    ) -> str:
        return hashlib.sha256(
            str(value).encode(
                "utf-8"
            )
        ).hexdigest()

    @classmethod
    def hash_path(
        cls,
        path: Path,
    ) -> str:
        return cls.hash_text(
            path.read_text(
                encoding="utf-8"
            )
        )

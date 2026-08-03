from __future__ import annotations

from pathlib import Path
from typing import Any

from app.code.code_parser import CodeParser
from app.code.project_scanner import ProjectScanner
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class SymbolIndex:

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        cache_file: str | Path | None = None,
        scanner: object | None = None,
        parser: object | None = None,
    ) -> None:
        paths = ProjectPaths.from_value(
            project_root
        )
        self.scanner = scanner or ProjectScanner()
        self.parser = parser or CodeParser()
        self.index: dict[str, Any] | None = None
        self.cache_file = (
            Path(cache_file)
            if cache_file is not None
            else paths.symbol_index_cache
        ).expanduser().resolve(
            strict=False
        )
        self._store = JsonStore(
            self.cache_file,
            self._empty_index,
        )

    @staticmethod
    def _empty_index(
    ) -> dict[str, list[Any]]:
        return {
            "classes": [],
            "functions": [],
            "imports": [],
        }

    def build(
        self,
    ):
        classes = []
        functions = []
        imports = []

        for path in self.scanner.list_python_files():
            parsed = self.parser.parse_file(
                path
            )

            if parsed.get(
                "error"
            ):
                continue

            for cls in parsed.get(
                "classes",
                [],
            ):
                classes.append(
                    {
                        "name": cls["name"],
                        "path": path,
                        "line": cls["line"],
                        "methods": cls.get(
                            "methods",
                            [],
                        ),
                    }
                )

            for func in parsed.get(
                "functions",
                [],
            ):
                functions.append(
                    {
                        "name": func["name"],
                        "path": path,
                        "line": func["line"],
                    }
                )

            for imp in parsed.get(
                "imports",
                [],
            ):
                imports.append(
                    {
                        **imp,
                        "path": path,
                    }
                )

        self.index = {
            "classes": classes,
            "functions": functions,
            "imports": imports,
        }
        self._save_cache()
        return self.index

    def get_index(
        self,
    ):
        if self.index is not None:
            return self.index

        cached = self._load_cache()

        if cached is not None:
            self.index = cached
            return self.index

        return self.build()

    def rebuild(
        self,
    ):
        self.index = None
        return self.build()

    def find_class(
        self,
        name: str,
    ):
        normalized = name.lower().strip()

        return [
            item
            for item in self.get_index()["classes"]
            if normalized
            in item["name"].lower()
        ]

    def find_function(
        self,
        name: str,
    ):
        normalized = name.lower().strip()

        return [
            item
            for item in self.get_index()["functions"]
            if normalized
            in item["name"].lower()
        ]

    def summary(
        self,
    ):
        index = self.get_index()

        return (
            "SYMBOL INDEX\n"
            f"Klasy: {len(index['classes'])}\n"
            f"Funkcje: {len(index['functions'])}\n"
            f"Importy: {len(index['imports'])}\n"
            f"Cache: {self.cache_file}"
        )

    def _save_cache(
        self,
    ):
        if self.index is None:
            return

        self._store.save(
            self.index
        )

    def _load_cache(
        self,
    ):
        if not self._store.exists():
            return None

        data = self._store.load()

        if not isinstance(
            data,
            dict,
        ):
            return None

        required = (
            "classes",
            "functions",
            "imports",
        )

        if any(
            not isinstance(
                data.get(key),
                list,
            )
            for key in required
        ):
            return None

        return data

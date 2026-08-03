from __future__ import annotations

import ast

from .source_index import SourceFile


class StructureAnalyzer:

    def large_files(
        self,
        files: list[SourceFile],
        threshold: int,
    ) -> dict[str, int]:
        return {
            str(item.path): item.line_count
            for item in files
            if item.line_count > threshold
        }

    def large_classes(
        self,
        files: list[SourceFile],
        method_threshold: int,
    ) -> dict[str, int]:
        results: dict[str, int] = {}

        for item in files:
            for node in item.tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue

                method_count = sum(
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    for child in node.body
                )

                if method_count > method_threshold:
                    key = f"{item.path}:{node.name}"
                    results[key] = method_count

        return results

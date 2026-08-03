from __future__ import annotations

import ast
from collections import defaultdict

from .source_index import SourceFile


class DependencyAnalyzer:

    def build_graph(
        self,
        files: list[SourceFile],
    ) -> dict[str, set[str]]:
        known_modules = {item.module for item in files}
        graph: dict[str, set[str]] = {
            item.module: set()
            for item in files
        }

        for item in files:
            for node in ast.walk(item.tree):
                for imported in self._imports_from_node(
                    node=node,
                    current_module=item.module,
                ):
                    target = self._resolve_known_module(
                        imported,
                        known_modules,
                    )
                    if target and target != item.module:
                        graph[item.module].add(target)

        return graph

    def coupling(
        self,
        graph: dict[str, set[str]],
    ) -> dict[str, int]:
        incoming: dict[str, set[str]] = defaultdict(set)

        for module, dependencies in graph.items():
            for dependency in dependencies:
                incoming[dependency].add(module)

        return {
            module: len(graph.get(module, set())) + len(incoming[module])
            for module in graph
        }

    def find_cycles(
        self,
        graph: dict[str, set[str]],
    ) -> list[list[str]]:
        cycles: set[tuple[str, ...]] = set()

        for start in graph:
            self._walk(
                graph=graph,
                start=start,
                current=start,
                path=[],
                cycles=cycles,
            )

        return [list(cycle) for cycle in sorted(cycles)]

    def _walk(
        self,
        graph: dict[str, set[str]],
        start: str,
        current: str,
        path: list[str],
        cycles: set[tuple[str, ...]],
    ) -> None:
        if current in path:
            return

        next_path = [*path, current]

        for dependency in graph.get(current, set()):
            if dependency == start and len(next_path) > 1:
                cycles.add(self._canonical_cycle(next_path))
                continue

            if dependency in graph and len(next_path) <= len(graph):
                self._walk(
                    graph,
                    start,
                    dependency,
                    next_path,
                    cycles,
                )

    @staticmethod
    def _canonical_cycle(
        cycle: list[str],
    ) -> tuple[str, ...]:
        rotations = [
            tuple(cycle[index:] + cycle[:index])
            for index in range(len(cycle))
        ]
        return min(rotations)

    @staticmethod
    def _imports_from_node(
        node: ast.AST,
        current_module: str,
    ) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]

        if isinstance(node, ast.ImportFrom):
            base = node.module or ""

            if node.level:
                package = current_module.split(".")[:-1]
                trim = max(node.level - 1, 0)

                if trim:
                    package = package[:-trim]

                base_parts = [*package]
                if base:
                    base_parts.extend(base.split("."))

                base = ".".join(base_parts)

            return [base] if base else []

        return []

    @staticmethod
    def _resolve_known_module(
        imported: str,
        known_modules: set[str],
    ) -> str | None:
        if imported in known_modules:
            return imported

        candidates = [
            module
            for module in known_modules
            if imported.startswith(f"{module}.")
            or module.startswith(f"{imported}.")
        ]

        if not candidates:
            return None

        return max(candidates, key=len)

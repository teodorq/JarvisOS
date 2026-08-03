from __future__ import annotations

import ast

from .source_index import SourceFile


class CohesionAnalyzer:

    def analyze(
        self,
        files: list[SourceFile],
    ) -> dict[str, dict[str, float | int]]:
        result: dict[str, dict[str, float | int]] = {}

        for item in files:
            for node in item.tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue

                methods = [
                    child
                    for child in node.body
                    if isinstance(
                        child,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                        ),
                    )
                ]

                if not methods:
                    continue

                attribute_sets = [
                    self._attributes_used(method)
                    for method in methods
                ]

                connected_pairs = 0
                total_pairs = 0

                for left_index in range(len(attribute_sets)):
                    for right_index in range(
                        left_index + 1,
                        len(attribute_sets),
                    ):
                        total_pairs += 1
                        if (
                            attribute_sets[left_index]
                            & attribute_sets[right_index]
                        ):
                            connected_pairs += 1

                cohesion = (
                    connected_pairs / total_pairs
                    if total_pairs
                    else 1.0
                )

                result[f"{item.module}.{node.name}"] = {
                    "methods": len(methods),
                    "connected_pairs": connected_pairs,
                    "total_pairs": total_pairs,
                    "cohesion": round(cohesion, 3),
                    "score": round(cohesion * 100.0, 2),
                }

        return result

    def low_cohesion_classes(
        self,
        metrics: dict[str, dict[str, float | int]],
        threshold: float = 0.35,
    ) -> dict[str, float]:
        return {
            class_name: float(values["cohesion"])
            for class_name, values in metrics.items()
            if float(values["cohesion"]) < threshold
        }

    @staticmethod
    def _attributes_used(
        method: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> set[str]:
        attributes: set[str] = set()

        for node in ast.walk(method):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"
            ):
                attributes.add(node.attr)

        return attributes

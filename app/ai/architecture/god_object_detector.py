from __future__ import annotations

import ast
from dataclasses import dataclass

from .source_index import SourceFile


@dataclass(frozen=True)
class GodObjectFinding:
    module: str
    class_name: str
    file_path: str
    method_count: int
    attribute_count: int
    dependency_count: int
    responsibility_count: int
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "module": self.module,
            "class_name": self.class_name,
            "file_path": self.file_path,
            "method_count": self.method_count,
            "attribute_count": self.attribute_count,
            "dependency_count": self.dependency_count,
            "responsibility_count": self.responsibility_count,
            "score": self.score,
        }


class GodObjectDetector:

    def __init__(
        self,
        method_threshold: int = 18,
        attribute_threshold: int = 12,
        dependency_threshold: int = 8,
        responsibility_threshold: int = 5,
        score_threshold: float = 60.0,
    ) -> None:
        self.method_threshold = method_threshold
        self.attribute_threshold = attribute_threshold
        self.dependency_threshold = dependency_threshold
        self.responsibility_threshold = responsibility_threshold
        self.score_threshold = score_threshold

    def detect(
        self,
        files: list[SourceFile],
        dependency_graph: dict[str, set[str]],
    ) -> list[GodObjectFinding]:
        findings: list[GodObjectFinding] = []

        for item in files:
            dependency_count = len(
                dependency_graph.get(item.module, set())
            )

            for node in item.tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue

                method_count = self._method_count(node)
                attribute_count = len(
                    self._instance_attributes(node)
                )
                responsibility_count = len(
                    self._responsibility_prefixes(node)
                )

                score = self._score(
                    method_count=method_count,
                    attribute_count=attribute_count,
                    dependency_count=dependency_count,
                    responsibility_count=responsibility_count,
                )

                threshold_hit = any(
                    (
                        method_count > self.method_threshold,
                        attribute_count > self.attribute_threshold,
                        dependency_count > self.dependency_threshold,
                        responsibility_count > self.responsibility_threshold,
                    )
                )

                if threshold_hit and score >= self.score_threshold:
                    findings.append(
                        GodObjectFinding(
                            module=item.module,
                            class_name=node.name,
                            file_path=str(item.path),
                            method_count=method_count,
                            attribute_count=attribute_count,
                            dependency_count=dependency_count,
                            responsibility_count=responsibility_count,
                            score=score,
                        )
                    )

        return sorted(
            findings,
            key=lambda finding: (
                -finding.score,
                finding.module,
                finding.class_name,
            ),
        )

    def _score(
        self,
        method_count: int,
        attribute_count: int,
        dependency_count: int,
        responsibility_count: int,
    ) -> float:
        method_score = min(
            100.0,
            method_count / max(self.method_threshold, 1) * 100.0,
        )
        attribute_score = min(
            100.0,
            attribute_count / max(self.attribute_threshold, 1) * 100.0,
        )
        dependency_score = min(
            100.0,
            dependency_count / max(self.dependency_threshold, 1) * 100.0,
        )
        responsibility_score = min(
            100.0,
            responsibility_count
            / max(self.responsibility_threshold, 1)
            * 100.0,
        )

        score = (
            method_score * 0.35
            + attribute_score * 0.25
            + dependency_score * 0.20
            + responsibility_score * 0.20
        )

        return round(score, 2)

    @staticmethod
    def _method_count(
        node: ast.ClassDef,
    ) -> int:
        return sum(
            isinstance(
                child,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            for child in node.body
        )

    @staticmethod
    def _instance_attributes(
        node: ast.ClassDef,
    ) -> set[str]:
        attributes: set[str] = set()

        for child in ast.walk(node):
            if (
                isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and child.value.id == "self"
            ):
                attributes.add(child.attr)

        return attributes

    @staticmethod
    def _responsibility_prefixes(
        node: ast.ClassDef,
    ) -> set[str]:
        prefixes: set[str] = set()

        for child in node.body:
            if not isinstance(
                child,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue

            method_name = child.name.strip("_")
            if not method_name:
                continue

            prefixes.add(method_name.split("_", 1)[0])

        return prefixes

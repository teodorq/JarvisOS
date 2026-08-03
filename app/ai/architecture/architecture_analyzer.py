from __future__ import annotations

from pathlib import Path

from .dependency_analyzer import DependencyAnalyzer
from .models import ArchitectureIssue, ArchitectureReport
from .source_index import SourceIndex
from .structure_analyzer import StructureAnalyzer


class ArchitectureAnalyzer:

    def __init__(
        self,
        project_root: str | Path,
        source_root: str = "app",
        large_file_lines: int = 700,
        large_class_methods: int = 20,
        high_coupling_threshold: int = 8,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.source_root = source_root
        self.large_file_lines = large_file_lines
        self.large_class_methods = large_class_methods
        self.high_coupling_threshold = high_coupling_threshold

        self.source_index = SourceIndex(
            project_root=self.project_root,
            source_root=source_root,
        )
        self.dependencies = DependencyAnalyzer()
        self.structure = StructureAnalyzer()

    def analyze(self) -> ArchitectureReport:
        files = self.source_index.build()
        graph = self.dependencies.build_graph(files)
        coupling = self.dependencies.coupling(graph)
        cycles = self.dependencies.find_cycles(graph)

        high_coupling = {
            module: value
            for module, value in coupling.items()
            if value > self.high_coupling_threshold
        }
        large_files = self.structure.large_files(
            files,
            threshold=self.large_file_lines,
        )
        large_classes = self.structure.large_classes(
            files,
            method_threshold=self.large_class_methods,
        )

        issues = self._build_issues(
            cycles=cycles,
            high_coupling=high_coupling,
            large_files=large_files,
            large_classes=large_classes,
        )

        dependency_count = sum(
            len(dependencies)
            for dependencies in graph.values()
        )

        return ArchitectureReport(
            files_scanned=len(files),
            modules_scanned=len(graph),
            dependency_count=dependency_count,
            circular_dependencies=cycles,
            high_coupling_modules=high_coupling,
            large_files=large_files,
            large_classes=large_classes,
            issues=issues,
            architecture_score=self._score(issues),
        )

    @staticmethod
    def _build_issues(
        cycles: list[list[str]],
        high_coupling: dict[str, int],
        large_files: dict[str, int],
        large_classes: dict[str, int],
    ) -> list[ArchitectureIssue]:
        issues: list[ArchitectureIssue] = []

        for cycle in cycles:
            issues.append(
                ArchitectureIssue(
                    code="CIRCULAR_DEPENDENCY",
                    message="Wykryto cykliczną zależność modułów.",
                    severity="high",
                    details={"modules": cycle},
                )
            )

        for module, value in high_coupling.items():
            issues.append(
                ArchitectureIssue(
                    code="HIGH_COUPLING",
                    message=f"Moduł {module} ma zbyt wiele zależności.",
                    severity="medium",
                    details={"coupling": value},
                )
            )

        for path, lines in large_files.items():
            issues.append(
                ArchitectureIssue(
                    code="LARGE_FILE",
                    message="Plik przekracza zalecany rozmiar.",
                    severity="medium",
                    file_path=path,
                    details={"lines": lines},
                )
            )

        for key, methods in large_classes.items():
            file_path, class_name = key.rsplit(":", 1)
            issues.append(
                ArchitectureIssue(
                    code="LARGE_CLASS",
                    message=f"Klasa {class_name} ma zbyt wiele metod.",
                    severity="medium",
                    file_path=file_path,
                    details={
                        "class_name": class_name,
                        "methods": methods,
                    },
                )
            )

        return issues

    @staticmethod
    def _score(
        issues: list[ArchitectureIssue],
    ) -> float:
        penalties = {
            "high": 12.0,
            "medium": 5.0,
            "low": 2.0,
        }

        result = 100.0 - sum(
            penalties.get(issue.severity, 3.0)
            for issue in issues
        )

        return round(max(0.0, result), 2)

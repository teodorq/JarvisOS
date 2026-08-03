from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .analyzers import ProjectQualityAnalyzer
from .code_map_builder import CodeMapBuilder
from .dependency_graph import DependencyGraphBuilder
from .models import CodeIssue, KnowledgeReport, KnowledgeTask


class AutonomousKnowledgeEngine:
    def __init__(
        self,
        code_map_builder: CodeMapBuilder | None = None,
        dependency_builder: DependencyGraphBuilder | None = None,
        quality_analyzer: ProjectQualityAnalyzer | None = None,
    ) -> None:
        self.code_map_builder = code_map_builder or CodeMapBuilder()
        self.dependency_builder = dependency_builder or DependencyGraphBuilder()
        self.quality_analyzer = quality_analyzer or ProjectQualityAnalyzer()

    def analyze_project(self, project_root: str | Path) -> KnowledgeReport:
        root = Path(project_root).resolve()
        code_map = self.code_map_builder.build(root)
        dependency_graph = self.dependency_builder.build(root, code_map)
        issues = self.quality_analyzer.analyze(root, code_map)
        tasks = self._build_tasks(issues)
        scanned_files = sum(1 for path in root.rglob("*") if path.is_file())
        return KnowledgeReport(
            project_root=str(root),
            scanned_files=scanned_files,
            python_files=len(code_map),
            issues=issues,
            tasks=tasks,
            dependency_graph=dependency_graph,
            code_map=code_map,
        )

    def save_report(self, report: KnowledgeReport, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def to_autodev_tasks(self, report: KnowledgeReport) -> list[dict]:
        return [task.to_dict() for task in report.tasks]

    @staticmethod
    def _build_tasks(issues: list[CodeIssue]) -> list[KnowledgeTask]:
        grouped: dict[tuple[str, str], list[CodeIssue]] = {}
        for issue in issues:
            grouped.setdefault((issue.category, issue.path), []).append(issue)

        severity_priority = {"high": 90, "medium": 60, "low": 30}
        category_roi = {
            "missing_test": 0.90,
            "parse_error": 0.95,
            "duplicate_code": 0.75,
            "high_complexity": 0.80,
            "large_file": 0.70,
            "possible_dead_code": 0.55,
        }
        category_risk = {
            "missing_test": 0.20,
            "parse_error": 0.25,
            "duplicate_code": 0.55,
            "high_complexity": 0.60,
            "large_file": 0.65,
            "possible_dead_code": 0.45,
        }

        tasks: list[KnowledgeTask] = []
        for (category, path), category_issues in grouped.items():
            strongest = max(category_issues, key=lambda item: severity_priority.get(item.severity, 50))
            priority = severity_priority.get(strongest.severity, 50) + min(9, len(category_issues) - 1)
            title = AutonomousKnowledgeEngine._task_title(category, path)
            description = " ".join(issue.message for issue in category_issues[:3])
            tasks.append(
                KnowledgeTask(
                    title=title,
                    description=description,
                    priority=min(100, priority),
                    roi=category_roi.get(category, 0.5),
                    risk=category_risk.get(category, 0.5),
                    metadata={
                        "category": category,
                        "path": path,
                        "issue_count": len(category_issues),
                        "severity_counts": dict(Counter(item.severity for item in category_issues)),
                    },
                )
            )

        return sorted(tasks, key=lambda task: (-task.priority, -task.roi, task.risk, task.title))

    @staticmethod
    def _task_title(category: str, path: str) -> str:
        labels = {
            "missing_test": "Dodaj testy",
            "parse_error": "Napraw analizę składni",
            "duplicate_code": "Usuń duplikację",
            "high_complexity": "Uprość złożoną funkcję",
            "large_file": "Podziel duży moduł",
            "possible_dead_code": "Zweryfikuj martwy kod",
        }
        return f"{labels.get(category, 'Ulepsz moduł')}: {path}"

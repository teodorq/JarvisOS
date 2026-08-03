from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from typing import Any

from app.autodev.backlog_manager import BacklogManager
from app.autodev.module_analysis import (
    ModuleAnalysis,
    ModuleAnalyzer,
)
from app.autodev.problem_detector import ProblemDetector
from app.autodev.project_scanner import ProjectScanner
from app.autodev.task_prioritizer import TaskPrioritizer


class AutonomousPlanner:

    def __init__(
        self,
        project_root: str = default_project_root(),
        backlog: BacklogManager | None = None,
        max_tasks_per_scan: int = 50,
    ) -> None:

        self.project_root = project_root
        self.scanner = ProjectScanner(project_root)
        self.module_analyzer = ModuleAnalyzer()
        self.problem_detector = ProblemDetector()
        self.prioritizer = TaskPrioritizer()
        self.backlog = backlog or BacklogManager()
        self.max_tasks_per_scan = max(
            1,
            int(
                max_tasks_per_scan
            ),
        )
        self.last_result: dict[str, Any] | None = None

    def scan_and_plan(
        self,
        context_by_module: dict[
            str,
            dict[str, Any]
        ] | None = None,
    ) -> dict[str, Any]:

        contexts = dict(
            context_by_module
            or {}
        )

        try:
            scan_report = self.scanner.scan_with_report()
            project_index = scan_report["index"]

            analyses = self.module_analyzer.analyze_many(
                project_index.files
            )

            problems = self.problem_detector.detect_many(
                analyses
            )

            ordered = self.prioritizer.prioritize(
                problems,
                contexts,
            )

            selected_problems = ordered[
                :self.max_tasks_per_scan
            ]

            tasks = [
                self.prioritizer.build_task(
                    problem,
                    contexts.get(
                        problem.module,
                        {},
                    ),
                )
                for problem in selected_problems
            ]

            fallback_used = False

            if not tasks:
                tasks = self._build_fallback_tasks(
                    analyses
                )
                fallback_used = bool(tasks)

            backlog_items = self.backlog.add_many(
                tasks
            )

            next_item = self.backlog.next_item()

            result = {
                "success": True,
                "status": (
                    "TASKS_PLANNED"
                    if next_item
                    else "NO_TASKS"
                ),
                "files_scanned": scan_report[
                    "files_count"
                ],
                "scan_errors": scan_report["errors"],
                "analyses_count": len(analyses),
                "problems_count": len(problems),
                "generated_tasks_count": len(tasks),
                "fallback_used": fallback_used,
                "backlog_count": len(
                    self.backlog.items
                ),
                "active_backlog_count": (
                    self.backlog.summary().get(
                        "active",
                        0,
                    )
                ),
                "pending_count": len(
                    self.backlog.list_items(
                        status="PENDING"
                    )
                ),
                "next_task": (
                    next_item.to_dict()
                    if next_item
                    else None
                ),
                "tasks": [
                    item.to_dict()
                    for item in backlog_items
                ],
            }

        except Exception as error:
            result = {
                "success": False,
                "status": "SCAN_AND_PLAN_FAILED",
                "files_scanned": 0,
                "scan_errors": [
                    f"{type(error).__name__}: {error}"
                ],
                "analyses_count": 0,
                "problems_count": 0,
                "generated_tasks_count": 0,
                "fallback_used": False,
                "backlog_count": len(
                    self.backlog.items
                ),
                "pending_count": len(
                    self.backlog.list_items(
                        status="PENDING"
                    )
                ),
                "next_task": None,
                "tasks": [],
            }

        self.last_result = dict(result)

        return result

    def _build_fallback_tasks(
        self,
        analyses: list[ModuleAnalysis],
    ) -> list[dict[str, Any]]:

        candidates = [
            analysis
            for analysis in analyses
            if self._is_safe_project_module(
                analysis.path
            )
        ]

        if not candidates:
            return []

        ordered = sorted(
            candidates,
            key=lambda analysis: (
                analysis.line_count,
                analysis.function_count,
                analysis.import_count,
            ),
            reverse=True,
        )

        selected = ordered[0]

        return [
            {
                "title": (
                    "Przegląd jakości i testów modułu"
                ),
                "description": (
                    "Przeanalizuj moduł, wykryj "
                    "najbezpieczniejsze ulepszenie "
                    "oraz przygotuj zmianę możliwą "
                    "do zweryfikowania testami."
                ),
                "target": selected.path,
                "recommendation": (
                    "Preferuj małą zmianę o niskim "
                    "ryzyku: poprawę walidacji, "
                    "obsługi błędów, czytelności "
                    "lub pokrycia testami."
                ),
                "severity": "LOW",
                "priority_score": self._fallback_score(
                    selected
                ),
                "source": "AutonomousPlannerFallback",
                "metadata": {
                    "fallback": True,
                    "reason": (
                        "Skan projektu nie wykrył "
                        "problemów regułowych."
                    ),
                    "line_count": selected.line_count,
                    "function_count": (
                        selected.function_count
                    ),
                    "class_count": selected.class_count,
                    "import_count": selected.import_count,
                    "analysis_score": selected.score,
                    "quality": selected.quality,
                    "risk": selected.risk,
                },
            }
        ]

    @staticmethod
    def _fallback_score(
        analysis: ModuleAnalysis,
    ) -> float:

        complexity = (
            min(
                analysis.line_count / 100.0,
                20.0,
            )
            + min(
                float(analysis.function_count),
                10.0,
            )
            + min(
                float(analysis.import_count),
                10.0,
            )
        )

        return round(
            20.0 + complexity,
            2,
        )

    @staticmethod
    def _is_safe_project_module(
        path: str,
    ) -> bool:

        normalized = str(path).replace(
            "\\",
            "/",
        ).casefold()

        excluded_parts = (
            "/.venv/",
            "/venv/",
            "/data/",
            "/archive/",
            "/backups/",
            "/__pycache__/",
            "/ai_pliki/",
            "/site-packages/",
        )

        if any(
            part in normalized
            for part in excluded_parts
        ):
            return False

        return (
            normalized.endswith(".py")
            and (
                "/app/" in normalized
                or normalized.startswith("app/")
            )
        )

    def next_task(
        self,
    ) -> dict[str, Any]:

        item = self.backlog.next_item()

        if item is None:
            return {
                "success": True,
                "status": "NO_TASKS",
                "task": None,
            }

        return {
            "success": True,
            "status": "READY",
            "task": item.to_dict(),
        }

    def claim_next_task(
        self,
    ) -> dict[str, Any]:

        item = self.backlog.next_item()

        if item is None:
            return {
                "success": True,
                "status": "NO_TASKS",
                "task": None,
            }

        item = self.backlog.mark_running(
            item.task_id
        )

        return {
            "success": True,
            "status": item.status,
            "task": item.to_dict(),
        }

    def complete_task(
        self,
        task_id: str,
    ) -> dict[str, Any]:

        item = self.backlog.mark_completed(
            task_id
        )

        return {
            "success": True,
            "status": item.status,
            "task": item.to_dict(),
        }

    def fail_task(
        self,
        task_id: str,
        error: str,
    ) -> dict[str, Any]:

        item = self.backlog.mark_failed(
            task_id,
            error,
        )

        return {
            "success": False,
            "status": item.status,
            "task": item.to_dict(),
        }

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": self.project_root,
            "backlog": self.backlog.summary(),
            "max_tasks_per_scan": (
                self.max_tasks_per_scan
            ),
            "last_result": self.last_result,
        }

from __future__ import annotations

from typing import Any

from app.autodev.backlog_manager import BacklogManager
from app.autodev.module_analysis import ModuleAnalyzer
from app.autodev.problem_detector import ProblemDetector
from app.autodev.project_scanner import ProjectScanner
from app.autodev.task_prioritizer import TaskPrioritizer


class AutonomousPlanner:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        backlog: BacklogManager | None = None,
    ) -> None:

        self.project_root = project_root
        self.scanner = ProjectScanner(project_root)
        self.module_analyzer = ModuleAnalyzer()
        self.problem_detector = ProblemDetector()
        self.prioritizer = TaskPrioritizer()
        self.backlog = backlog or BacklogManager()
        self.last_result: dict[str, Any] | None = None

    def scan_and_plan(
        self,
        context_by_module: dict[
            str,
            dict[str, Any]
        ] | None = None,
    ) -> dict[str, Any]:

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
            context_by_module,
        )

        tasks = [
            self.prioritizer.build_task(
                problem,
                (context_by_module or {}).get(
                    problem.module,
                    {},
                ),
            )
            for problem in ordered
        ]

        backlog_items = self.backlog.add_many(tasks)
        next_item = self.backlog.next_item()

        result = {
            "success": True,
            "files_scanned": scan_report["files_count"],
            "scan_errors": scan_report["errors"],
            "analyses_count": len(analyses),
            "problems_count": len(problems),
            "backlog_count": len(self.backlog.items),
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

        self.last_result = dict(result)

        return result

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

        item = self.backlog.mark_completed(task_id)

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
            "last_result": self.last_result,
        }

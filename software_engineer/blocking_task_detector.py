from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import ImplementationPlan


@dataclass(frozen=True)
class BlockingTaskFinding:
    task_id: str
    title: str
    blocked_by: tuple[str, ...]
    failed_dependencies: tuple[str, ...]
    dependent_tasks: tuple[str, ...]
    blocking_power: int
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "blocked_by": list(self.blocked_by),
            "failed_dependencies": list(self.failed_dependencies),
            "dependent_tasks": list(self.dependent_tasks),
            "blocking_power": self.blocking_power,
            "severity": self.severity,
        }


class BlockingTaskDetector:

    def analyze(
        self,
        plan: ImplementationPlan,
        *,
        completed_task_ids: Iterable[str] | None = None,
        failed_task_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        completed = set(completed_task_ids or ())
        failed = set(failed_task_ids or ())
        task_map = {task.task_id: task for task in plan.tasks}

        unknown = (completed | failed) - set(task_map)
        if unknown:
            raise ValueError(
                f"Unknown task identifiers: {sorted(unknown)}"
            )

        dependents = self._dependents(plan)
        findings: list[BlockingTaskFinding] = []

        for task in plan.tasks:
            if task.task_id in completed:
                continue

            missing = tuple(
                dependency
                for dependency in task.dependencies
                if dependency not in completed
            )
            failed_dependencies = tuple(
                dependency
                for dependency in missing
                if dependency in failed
            )

            if not missing:
                continue

            blocking_power = len(
                dependents.get(task.task_id, set())
            )

            findings.append(
                BlockingTaskFinding(
                    task_id=task.task_id,
                    title=task.title,
                    blocked_by=missing,
                    failed_dependencies=failed_dependencies,
                    dependent_tasks=tuple(
                        sorted(
                            dependents.get(
                                task.task_id,
                                set(),
                            )
                        )
                    ),
                    blocking_power=blocking_power,
                    severity=self._severity(
                        failed_dependencies=failed_dependencies,
                        blocking_power=blocking_power,
                    ),
                )
            )

        findings.sort(
            key=lambda item: (
                0 if item.severity == "critical" else 1,
                0 if item.severity == "high" else 1,
                -item.blocking_power,
                item.task_id,
            )
        )

        return {
            "blocked_count": len(findings),
            "hard_blocked_count": sum(
                bool(item.failed_dependencies)
                for item in findings
            ),
            "findings": [
                item.to_dict()
                for item in findings
            ],
        }

    @staticmethod
    def _severity(
        *,
        failed_dependencies: tuple[str, ...],
        blocking_power: int,
    ) -> str:
        if failed_dependencies:
            return "critical"
        if blocking_power >= 3:
            return "high"
        if blocking_power >= 1:
            return "medium"
        return "low"

    @staticmethod
    def _dependents(
        plan: ImplementationPlan,
    ) -> dict[str, set[str]]:
        direct: dict[str, set[str]] = {
            task.task_id: set()
            for task in plan.tasks
        }

        for task in plan.tasks:
            for dependency in task.dependencies:
                direct.setdefault(
                    dependency,
                    set(),
                ).add(task.task_id)

        result: dict[str, set[str]] = {}

        for task_id in direct:
            visited: set[str] = set()
            stack = list(direct.get(task_id, set()))

            while stack:
                child = stack.pop()
                if child in visited:
                    continue

                visited.add(child)
                stack.extend(
                    direct.get(child, set())
                )

            result[task_id] = visited

        return result

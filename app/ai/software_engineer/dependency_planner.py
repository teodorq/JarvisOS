from __future__ import annotations

from collections import defaultdict, deque

from .models import ImplementationTask


class DependencyPlanner:

    def validate(
        self,
        tasks: list[ImplementationTask],
    ) -> None:
        task_ids = {
            task.task_id
            for task in tasks
        }

        for task in tasks:
            unknown = [
                dependency
                for dependency in task.dependencies
                if dependency not in task_ids
            ]

            if unknown:
                raise ValueError(
                    f"Unknown dependencies for "
                    f"{task.task_id}: {unknown}"
                )

            if task.task_id in task.dependencies:
                raise ValueError(
                    "Task cannot depend on itself: "
                    f"{task.task_id}"
                )

        self.topological_order(tasks)

    def topological_order(
        self,
        tasks: list[ImplementationTask],
    ) -> list[str]:
        graph: dict[str, list[str]] = defaultdict(list)
        indegree = {
            task.task_id: 0
            for task in tasks
        }

        for task in tasks:
            for dependency in task.dependencies:
                graph[dependency].append(
                    task.task_id
                )
                indegree[task.task_id] += 1

        ready = deque(
            sorted(
                task_id
                for task_id, degree
                in indegree.items()
                if degree == 0
            )
        )
        result: list[str] = []

        while ready:
            task_id = ready.popleft()
            result.append(task_id)

            for child in sorted(
                graph.get(task_id, [])
            ):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)

        if len(result) != len(tasks):
            raise ValueError(
                "Circular dependency detected "
                "in implementation plan"
            )

        return result

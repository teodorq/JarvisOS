from __future__ import annotations

from .models import ImplementationTask


class ParallelExecutionPlanner:

    def build_groups(
        self,
        tasks: list[ImplementationTask],
    ) -> list[list[str]]:
        remaining = {
            task.task_id: task
            for task in tasks
        }
        completed: set[str] = set()
        groups: list[list[str]] = []

        while remaining:
            ready = sorted(
                task_id
                for task_id, task
                in remaining.items()
                if set(task.dependencies).issubset(
                    completed
                )
            )

            if not ready:
                raise ValueError(
                    "Unable to build parallel groups "
                    "because dependencies are cyclic"
                )

            group_index = len(groups)

            for task_id in ready:
                remaining[
                    task_id
                ].parallel_group = group_index

            groups.append(ready)
            completed.update(ready)

            for task_id in ready:
                remaining.pop(task_id)

        return groups

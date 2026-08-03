from __future__ import annotations

from typing import Any

from .models import ImplementationPlan


class ImplementationGraph:

    @staticmethod
    def build(
        plan: ImplementationPlan,
    ) -> dict[str, Any]:
        nodes = [
            {
                "id": task.task_id,
                "title": task.title,
                "category": task.category,
                "priority": task.priority,
                "parallel_group": task.parallel_group,
                "roi": task.estimated_roi,
                "risk": task.estimated_risk,
            }
            for task in plan.tasks
        ]

        edges = [
            {
                "from": dependency,
                "to": task.task_id,
            }
            for task in plan.tasks
            for dependency in task.dependencies
        ]

        return {
            "objective": plan.objective,
            "nodes": nodes,
            "edges": edges,
            "execution_order": list(
                plan.execution_order
            ),
            "parallel_groups": [
                list(group)
                for group in plan.parallel_groups
            ],
        }

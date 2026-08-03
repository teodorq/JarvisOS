from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.ai.software_engineer import (
    DecompositionController,
    DependencyPlanner,
    ImplementationGraph,
    ImplementationTask,
    TaskDecompositionEngine,
)


class FakeQueue:

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_unique_task(self, **kwargs):
        self.calls.append(kwargs)
        task = SimpleNamespace(
            task_id=f"queue-{len(self.calls)}"
        )
        return task, True


class TaskDecompositionTests(unittest.TestCase):

    def test_decomposes_large_goal_into_ordered_tasks(self) -> None:
        plan = TaskDecompositionEngine().decompose(
            "Dodaj moduł Trading AI"
        )

        self.assertGreaterEqual(
            len(plan.tasks),
            8,
        )
        self.assertEqual(
            len(plan.execution_order),
            len(plan.tasks),
        )
        self.assertEqual(
            plan.tasks[0].category,
            "analysis",
        )

    def test_tasks_have_roi_risk_time_and_acceptance_criteria(self) -> None:
        plan = TaskDecompositionEngine().decompose(
            "Dodaj nowy system raportów"
        )

        for task in plan.tasks:
            self.assertGreater(
                task.estimated_minutes,
                0,
            )
            self.assertGreaterEqual(
                task.estimated_roi,
                0.0,
            )
            self.assertLessEqual(
                task.estimated_risk,
                1.0,
            )
            self.assertTrue(
                task.acceptance_criteria
            )

    def test_parallel_groups_are_generated(self) -> None:
        plan = TaskDecompositionEngine().decompose(
            "Dodaj obsługę nowego API"
        )

        self.assertGreater(
            len(plan.parallel_groups),
            1,
        )
        flattened = [
            task_id
            for group in plan.parallel_groups
            for task_id in group
        ]
        self.assertEqual(
            set(flattened),
            {
                task.task_id
                for task in plan.tasks
            },
        )

    def test_dependency_planner_rejects_cycle(self) -> None:
        tasks = [
            ImplementationTask(
                task_id="a",
                title="A",
                description="A",
                category="test",
                priority="normal",
                estimated_minutes=1,
                estimated_roi=0.5,
                estimated_risk=0.5,
                dependencies=["b"],
            ),
            ImplementationTask(
                task_id="b",
                title="B",
                description="B",
                category="test",
                priority="normal",
                estimated_minutes=1,
                estimated_roi=0.5,
                estimated_risk=0.5,
                dependencies=["a"],
            ),
        ]

        with self.assertRaises(
            ValueError
        ):
            DependencyPlanner().validate(
                tasks
            )

    def test_implementation_graph_contains_nodes_and_edges(self) -> None:
        plan = TaskDecompositionEngine().decompose(
            "Dodaj eksport danych"
        )

        graph = ImplementationGraph.build(
            plan
        )

        self.assertEqual(
            len(graph["nodes"]),
            len(plan.tasks),
        )
        self.assertTrue(
            graph["edges"]
        )

    def test_controller_enqueues_tasks_with_dependencies(self) -> None:
        queue = FakeQueue()
        controller = DecompositionController(
            task_queue=queue
        )

        result = controller.create_plan(
            "Dodaj system alertów",
            enqueue=True,
        )

        self.assertTrue(
            result["queue"]["success"]
        )
        self.assertEqual(
            result["queue"]["created"],
            len(queue.calls),
        )
        self.assertEqual(
            queue.calls[0]["dependencies"],
            [],
        )
        self.assertTrue(
            any(
                call["dependencies"]
                for call in queue.calls[1:]
            )
        )

    def test_empty_objective_is_rejected(self) -> None:
        with self.assertRaises(
            ValueError
        ):
            TaskDecompositionEngine().decompose(
                "   "
            )


if __name__ == "__main__":
    unittest.main()

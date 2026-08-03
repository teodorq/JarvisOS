from __future__ import annotations

import unittest

from app.ai.software_engineer import (
    ImplementationPlan,
    ImplementationPlanner,
    ImplementationTask,
)


def task(
    task_id: str,
    *,
    roi: float,
    risk: float,
    priority: str = "normal",
    dependencies: list[str] | None = None,
) -> ImplementationTask:
    return ImplementationTask(
        task_id=task_id,
        title=task_id.upper(),
        description=task_id,
        category="implementation",
        priority=priority,
        estimated_minutes=10,
        estimated_roi=roi,
        estimated_risk=risk,
        dependencies=list(
            dependencies or []
        ),
    )


def plan(
    tasks: list[ImplementationTask],
) -> ImplementationPlan:
    return ImplementationPlan(
        objective="Build feature",
        tasks=tasks,
        execution_order=[
            item.task_id
            for item in tasks
        ],
        parallel_groups=[],
        total_estimated_minutes=10 * len(tasks),
        average_roi=0.5,
        average_risk=0.5,
    )


class ImplementationPlannerTests(unittest.TestCase):

    def test_selects_only_task_with_completed_dependencies(self) -> None:
        implementation_plan = plan(
            [
                task(
                    "analysis",
                    roi=0.7,
                    risk=0.1,
                ),
                task(
                    "code",
                    roi=1.0,
                    risk=0.1,
                    dependencies=["analysis"],
                ),
            ]
        )

        selected = ImplementationPlanner().select_next(
            implementation_plan
        )

        self.assertIsNotNone(selected)
        self.assertEqual(
            selected.task_id,
            "analysis",
        )

    def test_selects_high_roi_low_risk_ready_task(self) -> None:
        implementation_plan = plan(
            [
                task(
                    "weak",
                    roi=0.3,
                    risk=0.8,
                ),
                task(
                    "best",
                    roi=0.9,
                    risk=0.1,
                ),
            ]
        )

        selected = ImplementationPlanner().select_next(
            implementation_plan
        )

        self.assertEqual(
            selected.task_id,
            "best",
        )

    def test_blocking_power_improves_task_score(self) -> None:
        implementation_plan = plan(
            [
                task(
                    "foundation",
                    roi=0.6,
                    risk=0.2,
                ),
                task(
                    "isolated",
                    roi=0.6,
                    risk=0.2,
                ),
                task(
                    "child",
                    roi=0.7,
                    risk=0.2,
                    dependencies=["foundation"],
                ),
                task(
                    "grandchild",
                    roi=0.8,
                    risk=0.2,
                    dependencies=["child"],
                ),
            ]
        )

        selected = ImplementationPlanner().select_next(
            implementation_plan
        )

        self.assertEqual(
            selected.task_id,
            "foundation",
        )
        self.assertEqual(
            selected.blocking_power,
            2,
        )

    def test_failed_task_is_not_selected(self) -> None:
        implementation_plan = plan(
            [
                task(
                    "first",
                    roi=0.9,
                    risk=0.1,
                ),
                task(
                    "second",
                    roi=0.8,
                    risk=0.2,
                ),
            ]
        )

        selected = ImplementationPlanner().select_next(
            implementation_plan,
            failed_task_ids={"first"},
        )

        self.assertEqual(
            selected.task_id,
            "second",
        )

    def test_reports_hard_block_from_failed_dependency(self) -> None:
        implementation_plan = plan(
            [
                task(
                    "foundation",
                    roi=0.7,
                    risk=0.2,
                ),
                task(
                    "feature",
                    roi=0.9,
                    risk=0.2,
                    dependencies=["foundation"],
                ),
            ]
        )

        blocked = ImplementationPlanner().blocked_tasks(
            implementation_plan,
            failed_task_ids={"foundation"},
        )

        feature = next(
            item
            for item in blocked
            if item["task_id"] == "feature"
        )

        self.assertTrue(
            feature["hard_blocked"]
        )
        self.assertEqual(
            feature["failed_dependencies"],
            ["foundation"],
        )

    def test_iteration_returns_ranked_ready_tasks(self) -> None:
        implementation_plan = plan(
            [
                task(
                    "one",
                    roi=0.6,
                    risk=0.3,
                ),
                task(
                    "two",
                    roi=0.9,
                    risk=0.1,
                ),
                task(
                    "three",
                    roi=0.5,
                    risk=0.4,
                ),
            ]
        )

        iteration = ImplementationPlanner().plan_iteration(
            implementation_plan,
            max_tasks=2,
        )

        self.assertEqual(
            iteration["status"],
            "READY",
        )
        self.assertEqual(
            len(iteration["selected_tasks"]),
            2,
        )
        self.assertEqual(
            iteration["selected_tasks"][0][
                "task_id"
            ],
            "two",
        )

    def test_unknown_task_identifier_is_rejected(self) -> None:
        implementation_plan = plan(
            [
                task(
                    "known",
                    roi=0.5,
                    risk=0.5,
                )
            ]
        )

        with self.assertRaises(
            ValueError
        ):
            ImplementationPlanner().select_next(
                implementation_plan,
                completed_task_ids={"missing"},
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.ai.software_engineer import (
    BlockingTaskDetector,
    ImplementationPlan,
    ImplementationTask,
    IterationPlanner,
)


def make_task(
    task_id: str,
    *,
    dependencies: list[str] | None = None,
    minutes: int = 20,
    roi: float = 0.7,
    risk: float = 0.2,
) -> ImplementationTask:
    return ImplementationTask(
        task_id=task_id,
        title=task_id,
        description=task_id,
        category="implementation",
        priority="high",
        estimated_minutes=minutes,
        estimated_roi=roi,
        estimated_risk=risk,
        dependencies=list(dependencies or []),
        acceptance_criteria=["Done"],
    )


def make_plan(
    tasks: list[ImplementationTask],
) -> ImplementationPlan:
    return ImplementationPlan(
        objective="Build feature",
        tasks=tasks,
        execution_order=[
            task.task_id
            for task in tasks
        ],
        parallel_groups=[],
        total_estimated_minutes=sum(
            task.estimated_minutes
            for task in tasks
        ),
        average_roi=0.7,
        average_risk=0.2,
    )


class BlockingIterationTests(unittest.TestCase):

    def test_detects_blocked_task(self) -> None:
        plan = make_plan(
            [
                make_task("analysis"),
                make_task(
                    "implementation",
                    dependencies=["analysis"],
                ),
            ]
        )

        report = BlockingTaskDetector().analyze(plan)

        self.assertEqual(report["blocked_count"], 1)
        self.assertEqual(
            report["findings"][0]["task_id"],
            "implementation",
        )

    def test_failed_dependency_creates_critical_block(self) -> None:
        plan = make_plan(
            [
                make_task("analysis"),
                make_task(
                    "implementation",
                    dependencies=["analysis"],
                ),
            ]
        )

        report = BlockingTaskDetector().analyze(
            plan,
            failed_task_ids={"analysis"},
        )

        self.assertEqual(
            report["hard_blocked_count"],
            1,
        )
        self.assertEqual(
            report["findings"][0]["severity"],
            "critical",
        )

    def test_iteration_selects_ready_tasks(self) -> None:
        plan = make_plan(
            [
                make_task("analysis", roi=0.9),
                make_task("documentation", roi=0.5),
            ]
        )

        result = IterationPlanner().build_iteration(
            plan,
            max_tasks=2,
        )

        self.assertEqual(result["status"], "READY")
        self.assertEqual(
            result["iteration"]["task_count"],
            2,
        )

    def test_iteration_respects_time_limit(self) -> None:
        plan = make_plan(
            [
                make_task("one", minutes=80, roi=0.9),
                make_task("two", minutes=80, roi=0.8),
            ]
        )

        result = IterationPlanner().build_iteration(
            plan,
            max_tasks=2,
            max_estimated_minutes=100,
        )

        self.assertEqual(
            result["iteration"]["task_count"],
            1,
        )
        self.assertEqual(
            result["iteration"]["estimated_minutes"],
            80,
        )

    def test_completed_plan_returns_completed_status(self) -> None:
        plan = make_plan(
            [
                make_task("one"),
            ]
        )

        result = IterationPlanner().build_iteration(
            plan,
            completed_task_ids={"one"},
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )

    def test_hard_blocked_plan_returns_hard_blocked(self) -> None:
        plan = make_plan(
            [
                make_task("foundation"),
                make_task(
                    "feature",
                    dependencies=["foundation"],
                ),
            ]
        )

        result = IterationPlanner().build_iteration(
            plan,
            failed_task_ids={"foundation"},
        )

        self.assertEqual(
            result["status"],
            "HARD_BLOCKED",
        )

    def test_progress_counts_are_correct(self) -> None:
        plan = make_plan(
            [
                make_task("one"),
                make_task("two"),
                make_task("three"),
            ]
        )

        result = IterationPlanner().build_iteration(
            plan,
            completed_task_ids={"one"},
            failed_task_ids={"two"},
        )

        self.assertEqual(
            result["progress"],
            {
                "completed": 1,
                "failed": 1,
                "remaining": 1,
                "total": 3,
            },
        )


if __name__ == "__main__":
    unittest.main()

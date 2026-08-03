from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.ai.software_engineer import (
    DecompositionController,
    ImplementationPlan,
    ImplementationScheduler,
    ImplementationTask,
    SchedulerController,
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


def make_task(
    task_id: str,
    *,
    dependencies: list[str] | None = None,
    roi: float = 0.7,
    risk: float = 0.2,
    minutes: int = 20,
) -> ImplementationTask:
    return ImplementationTask(
        task_id=task_id,
        title=task_id.title(),
        description=f"Implement {task_id}",
        category="implementation",
        priority="high",
        estimated_minutes=minutes,
        estimated_roi=roi,
        estimated_risk=risk,
        dependencies=list(
            dependencies or []
        ),
        acceptance_criteria=[
            "Task completed.",
        ],
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


class SchedulerIntegrationTests(unittest.TestCase):

    def test_scheduler_selects_best_ready_task(self) -> None:
        plan = make_plan(
            [
                make_task(
                    "weak",
                    roi=0.3,
                    risk=0.8,
                ),
                make_task(
                    "best",
                    roi=0.9,
                    risk=0.1,
                ),
            ]
        )

        result = ImplementationScheduler().schedule_next(
            plan
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["scheduled_task"]["task_id"],
            "best",
        )

    def test_scheduler_does_not_select_blocked_task(self) -> None:
        plan = make_plan(
            [
                make_task("foundation"),
                make_task(
                    "feature",
                    dependencies=["foundation"],
                    roi=1.0,
                    risk=0.0,
                ),
            ]
        )

        result = ImplementationScheduler().schedule_next(
            plan
        )

        self.assertEqual(
            result["scheduled_task"]["task_id"],
            "foundation",
        )

    def test_scheduler_enqueues_selected_task(self) -> None:
        queue = FakeQueue()
        plan = make_plan(
            [
                make_task("implementation"),
            ]
        )

        result = ImplementationScheduler(
            task_queue=queue,
        ).schedule_next(
            plan,
            enqueue=True,
        )

        self.assertEqual(
            result["queue"]["created"],
            1,
        )
        self.assertEqual(
            queue.calls[0]["source"],
            "implementation_scheduler",
        )
        self.assertEqual(
            queue.calls[0]["payload"]["type"],
            "scheduled_implementation_task",
        )

    def test_iteration_scheduler_respects_limits(self) -> None:
        plan = make_plan(
            [
                make_task(
                    "one",
                    roi=0.9,
                    minutes=70,
                ),
                make_task(
                    "two",
                    roi=0.8,
                    minutes=70,
                ),
                make_task(
                    "three",
                    roi=0.7,
                    minutes=20,
                ),
            ]
        )

        result = ImplementationScheduler().schedule_iteration(
            plan,
            max_tasks=3,
            max_estimated_minutes=100,
        )

        self.assertTrue(result["success"])
        self.assertLessEqual(
            sum(
                item["estimated_minutes"]
                for item in result["scheduled_tasks"]
            ),
            100,
        )

    def test_scheduler_controller_requires_plan(self) -> None:
        controller = SchedulerController()

        result = controller.handle(
            "zaplanuj następną iterację",
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "PLAN_REQUIRED",
        )

    def test_scheduler_controller_handles_next_mode(self) -> None:
        plan = make_plan(
            [
                make_task("analysis"),
            ]
        )

        result = SchedulerController().handle(
            "wybierz następne zadanie",
            plan=plan,
            context={
                "mode": "next",
                "enqueue": False,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["scheduled_task"]["task_id"],
            "analysis",
        )

    def test_decomposition_controller_creates_and_schedules(self) -> None:
        result = DecompositionController().create_and_schedule(
            "Dodaj moduł raportowania",
            enqueue=False,
            max_tasks=2,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PLANNED_AND_SCHEDULED",
        )
        self.assertEqual(
            result["scheduling"]["status"],
            "READY",
        )
        self.assertGreater(
            len(
                result["scheduling"][
                    "scheduled_tasks"
                ]
            ),
            0,
        )

    def test_decomposition_controller_reports_unsupported_mode(self) -> None:
        controller = DecompositionController()
        plan = controller.engine.decompose(
            "Dodaj moduł raportowania"
        )

        result = controller.schedule_plan(
            plan,
            mode="unknown",
            enqueue=False,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "UNSUPPORTED_MODE",
        )


if __name__ == "__main__":
    unittest.main()

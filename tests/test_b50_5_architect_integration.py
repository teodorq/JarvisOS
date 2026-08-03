from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.ai.architecture import (
    ArchitectController,
    AutonomousArchitect,
)


class FakeEvolutionController:

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_and_start(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "status": "RUNNING",
        }


class FakeDirectorController:

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def plan_project_autonomously(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "status": "PLANNED",
        }


class FakeQueue:

    def __init__(self) -> None:
        self.tasks: list[dict[str, object]] = []

    def create_unique_task(self, **kwargs):
        self.tasks.append(kwargs)
        task = SimpleNamespace(
            task_id=f"task-{len(self.tasks)}"
        )
        return task, True


class ArchitectIntegrationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "app").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(
        self,
        relative_path: str,
        content: str,
    ) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def create_large_file(self) -> None:
        self.write(
            "app/large.py",
            "\n".join(
                f"value_{index} = {index}"
                for index in range(710)
            ),
        )

    def test_ranks_higher_roi_and_lower_risk_first(self) -> None:
        ranked = AutonomousArchitect._rank_blueprints(
            [
                {
                    "title": "weak",
                    "estimated_roi": 0.4,
                    "estimated_risk": 0.8,
                    "priority": "medium",
                },
                {
                    "title": "best",
                    "estimated_roi": 0.9,
                    "estimated_risk": 0.2,
                    "priority": "high",
                },
            ]
        )

        self.assertEqual(ranked[0]["title"], "best")
        self.assertIn("architect_score", ranked[0])

    def test_integrates_with_evolution_and_director(self) -> None:
        self.create_large_file()
        evolution = FakeEvolutionController()
        director = FakeDirectorController()

        result = AutonomousArchitect(
            self.root,
            evolution_controller=evolution,
            director_controller=director,
        ).analyze_and_plan()

        self.assertTrue(result["success"])
        self.assertEqual(len(evolution.calls), 1)
        self.assertEqual(len(director.calls), 1)
        self.assertEqual(
            result["evolution"]["status"],
            "RUNNING",
        )
        self.assertEqual(
            result["director"]["status"],
            "PLANNED",
        )

    def test_enqueues_blueprints_in_autodev_queue(self) -> None:
        self.create_large_file()
        queue = FakeQueue()

        result = AutonomousArchitect(
            self.root,
            task_queue=queue,
        ).analyze_and_plan(
            enqueue=True,
        )

        self.assertGreater(
            result["autodev_queue"]["created"],
            0,
        )
        self.assertTrue(queue.tasks)
        self.assertEqual(
            queue.tasks[0]["source"],
            "autonomous_architect",
        )

    def test_queue_unavailable_is_reported_safely(self) -> None:
        architect = AutonomousArchitect(
            self.root,
        )

        result = architect.enqueue_blueprints(
            [
                {
                    "title": "Refactor",
                    "objective": "Improve architecture",
                }
            ]
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "QUEUE_UNAVAILABLE",
        )

    def test_controller_handles_architect_command(self) -> None:
        self.create_large_file()
        queue = FakeQueue()

        controller = ArchitectController(
            self.root,
            task_queue=queue,
        )

        result = controller.handle(
            "autonomous architect",
            {
                "enqueue": True,
                "limit": 3,
            },
        )

        self.assertTrue(result["success"])
        self.assertGreaterEqual(
            result["recommended_count"],
            1,
        )

    def test_controller_rejects_unknown_command(self) -> None:
        controller = ArchitectController(
            self.root,
        )

        result = controller.handle(
            "otwórz kalkulator",
        )

        self.assertEqual(
            result["status"],
            "UNSUPPORTED_COMMAND",
        )


if __name__ == "__main__":
    unittest.main()

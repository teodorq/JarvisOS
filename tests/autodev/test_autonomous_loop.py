import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_loop import (
    AutonomousLoop,
    AutonomousLoopPolicy,
)
from app.autodev.autonomous_manager import AutonomousManager
from app.autodev.experience_memory import ExperienceMemory
from app.autodev.learning_engine import LearningEngine


class TestAutonomousLoop(unittest.TestCase):

    def test_stops_when_no_tasks(self) -> None:
        runtime = MagicMock()
        runtime.run_once.return_value = {
            "success": True,
            "status": "NO_TASKS",
        }

        loop = AutonomousLoop(
            runtime=runtime,
            policy=AutonomousLoopPolicy(
                max_cycles=5
            ),
        )

        result = loop.run()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["stop_reason"],
            "NO_TASKS",
        )
        self.assertEqual(result["cycles_run"], 1)

    def test_stops_on_failure(self) -> None:
        runtime = MagicMock()
        runtime.run_once.return_value = {
            "success": False,
            "status": "FAILED",
        }

        loop = AutonomousLoop(
            runtime=runtime,
            policy=AutonomousLoopPolicy(
                max_cycles=5,
                stop_on_failure=True,
            ),
        )

        result = loop.run()

        self.assertFalse(result["success"])
        self.assertEqual(
            result["stop_reason"],
            "FAILURE",
        )

    def test_learning_records_result(self) -> None:
        memory = ExperienceMemory()
        engine = LearningEngine(memory=memory)

        result = engine.learn_from_result(
            {
                "success": True,
                "status": "completed",
                "generation": {
                    "task": {
                        "task_id": "task-1",
                        "title": "Test task",
                        "target": "app/example.py",
                    }
                },
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(memory.summary()["total"], 1)

    def test_manager_can_start(self) -> None:
        loop = MagicMock()
        loop.run.return_value = {
            "success": True,
            "status": "STOPPED",
        }
        loop.status.return_value = {}

        manager = AutonomousManager(loop=loop)
        result = manager.start(max_cycles=2)

        self.assertTrue(result["success"])
        loop.run.assert_called_once_with(
            max_cycles=2,
            context=None,
        )


if __name__ == "__main__":
    unittest.main()

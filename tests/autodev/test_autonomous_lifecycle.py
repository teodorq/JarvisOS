import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.autodev.autonomous_lifecycle import AutonomousLifecycle
from app.autodev.lifecycle_state import LifecycleStateStore


class TestAutonomousLifecycle(unittest.TestCase):

    def test_returns_no_tasks(self) -> None:
        controller = MagicMock()
        controller.list_tasks.return_value = []

        manager = MagicMock()
        manager.status.return_value = {}

        with tempfile.TemporaryDirectory() as directory:
            lifecycle = AutonomousLifecycle(
                controller=controller,
                manager=manager,
                state_store=LifecycleStateStore(
                    str(
                        Path(directory)
                        / "state.json"
                    )
                ),
            )

            result = lifecycle.run_next()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "NO_TASKS",
        )
        manager.start.assert_not_called()

    def test_runs_selected_task(self) -> None:
        controller = MagicMock()
        controller.list_tasks.return_value = [
            {
                "task_id": "task-1",
                "priority": "HIGH",
                "status": "PENDING",
            }
        ]

        manager = MagicMock()
        manager.start.return_value = {
            "success": True,
            "status": "STOPPED",
        }
        manager.status.return_value = {}

        with tempfile.TemporaryDirectory() as directory:
            lifecycle = AutonomousLifecycle(
                controller=controller,
                manager=manager,
                state_store=LifecycleStateStore(
                    str(
                        Path(directory)
                        / "state.json"
                    )
                ),
            )

            result = lifecycle.run_next()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["selected_task"]["task_id"],
            "task-1",
        )
        manager.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()

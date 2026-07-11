import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_executor import AutonomousExecutor
from app.autodev.autonomous_service import AutonomousService


class TestAutonomousRuntime(unittest.TestCase):

    def test_executor_starts_manager(self) -> None:
        manager = MagicMock()
        manager.start.return_value = {
            "success": True,
            "status": "STOPPED",
        }

        executor = AutonomousExecutor(manager=manager)

        result = executor.start(max_cycles=2)

        self.assertTrue(result["success"])
        manager.start.assert_called_once_with(
            max_cycles=2,
            context=None,
        )

    def test_executor_rejects_unknown_action(self) -> None:
        executor = AutonomousExecutor(
            manager=MagicMock()
        )

        result = executor.execute("unknown")

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "UNKNOWN_ACTION",
        )

    def test_service_runs_synchronously(self) -> None:
        executor = MagicMock()
        executor.start.return_value = {
            "success": True,
            "status": "STOPPED",
        }
        executor.status.return_value = {}

        service = AutonomousService(
            executor=executor
        )

        result = service.start(
            max_cycles=1,
            background=False,
        )

        self.assertTrue(result["success"])
        executor.start.assert_called_once_with(
            max_cycles=1,
            context=None,
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_policy import BackgroundAutonomyPolicy
from app.autodev.background_worker import BackgroundWorker


class TestBackgroundWorker(unittest.TestCase):

    def test_skips_when_triggers_block(self) -> None:
        service = MagicMock()
        service.is_running.return_value = False

        triggers = MagicMock()
        triggers.evaluate.return_value = {
            "allowed": False,
            "reasons": ["busy"],
        }

        worker = BackgroundWorker(
            service=service,
            triggers=triggers,
            policy=BackgroundAutonomyPolicy(),
        )
        worker.enable()

        result = worker.tick()

        self.assertEqual(
            result["status"],
            "SKIPPED",
        )
        service.start.assert_not_called()

    def test_starts_when_allowed(self) -> None:
        service = MagicMock()
        service.is_running.return_value = False
        service.start.return_value = {
            "success": True,
            "status": "STARTED",
        }

        triggers = MagicMock()
        triggers.evaluate.return_value = {
            "allowed": True,
            "reasons": [],
        }

        worker = BackgroundWorker(
            service=service,
            triggers=triggers,
            policy=BackgroundAutonomyPolicy(
                max_cycles_per_run=2
            ),
        )
        worker.enable()

        result = worker.tick()

        self.assertTrue(result["success"])
        service.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()

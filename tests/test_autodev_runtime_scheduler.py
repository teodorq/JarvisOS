import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_cycle_executor import (
    AutoDevCycleExecutor,
)
from app.autodev.autodev_event_bus import AutoDevEventBus
from app.autodev.autodev_queue_service import (
    AutoDevQueueService,
)
from app.autodev.autodev_runtime_controller import (
    AutoDevRuntimeController,
)
from app.autodev.autodev_runtime_scheduler import (
    AutoDevRuntimeScheduler,
)


class TestAutoDevRuntimeScheduler(
    unittest.TestCase
):

    def test_schedule_and_run_next(
        self,
    ) -> None:
        runtime = MagicMock()
        runtime.run_goal.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        queue = AutoDevQueueService()
        executor = AutoDevCycleExecutor(
            runtime_service=runtime,
            event_bus=AutoDevEventBus(),
        )
        scheduler = AutoDevRuntimeScheduler(
            queue_service=queue,
            cycle_executor=executor,
        )

        queued = scheduler.schedule(
            "Ulepsz moduł testowy"
        )

        self.assertEqual(
            queued["status"],
            "QUEUED"
        )

        result = scheduler.run_next()

        self.assertTrue(
            result["success"]
        )
        self.assertFalse(
            result["writes_code"]
        )
        self.assertFalse(
            result["approved"]
        )

    def test_controller_queue_command(
        self,
    ) -> None:
        runtime = MagicMock()

        controller = AutoDevRuntimeController(
            runtime_service=runtime
        )

        result = controller.handle(
            "autodev runtime queue Ulepsz Brain"
        )

        self.assertEqual(
            result["status"],
            "QUEUED"
        )

    def test_controller_status(
        self,
    ) -> None:
        runtime = MagicMock()

        controller = AutoDevRuntimeController(
            runtime_service=runtime
        )

        result = controller.handle(
            "autodev runtime status"
        )

        self.assertEqual(
            result["status"],
            "RUNTIME_MONITOR_READY"
        )


if __name__ == "__main__":
    unittest.main()

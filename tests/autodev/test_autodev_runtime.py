import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_runtime import (
    AutoDevRuntime,
    AutoDevRuntimePolicy,
)


class TestAutoDevRuntime(unittest.TestCase):

    def test_stops_when_no_tasks(
        self,
    ) -> None:

        controller = MagicMock()
        controller.run_generation_cycle.return_value = {
            "success": True,
            "status": "NO_TASKS",
        }

        runtime = AutoDevRuntime(
            controller=controller,
            policy=AutoDevRuntimePolicy(
                max_cycles=5
            ),
        )

        result = runtime.run()

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["stop_reason"],
            "NO_TASKS",
        )
        self.assertEqual(
            result["cycles_run"],
            1,
        )

    def test_stops_when_code_is_required(
        self,
    ) -> None:

        controller = MagicMock()
        controller.run_generation_cycle.return_value = {
            "success": False,
            "status": "CODE_INPUT_REQUIRED",
        }

        runtime = AutoDevRuntime(
            controller=controller,
            policy=AutoDevRuntimePolicy(
                max_cycles=5,
                stop_when_code_required=True,
            ),
        )

        result = runtime.run()

        self.assertEqual(
            result["stop_reason"],
            "CODE_INPUT_REQUIRED",
        )
        self.assertEqual(
            result["cycles_run"],
            1,
        )

    def test_can_approve_and_execute(
        self,
    ) -> None:

        controller = MagicMock()
        controller.run_generation_cycle.return_value = {
            "success": True,
            "status": "waiting_for_approval",
        }
        controller.approve_generated_change.return_value = {
            "success": True,
            "status": "completed",
        }

        runtime = AutoDevRuntime(
            controller=controller,
            policy=AutoDevRuntimePolicy(
                max_cycles=1,
                auto_approve=True,
                auto_execute=True,
            ),
        )

        result = runtime.run()

        self.assertEqual(
            result["cycles_run"],
            1,
        )
        controller.approve_generated_change.assert_called_once_with(
            auto_execute=True
        )

    def test_respects_max_cycles(
        self,
    ) -> None:

        controller = MagicMock()
        controller.run_generation_cycle.return_value = {
            "success": True,
            "status": "waiting_for_approval",
        }

        runtime = AutoDevRuntime(
            controller=controller,
            policy=AutoDevRuntimePolicy(
                max_cycles=3,
                auto_approve=False,
            ),
        )

        result = runtime.run()

        self.assertEqual(
            result["stop_reason"],
            "MAX_CYCLES_REACHED",
        )
        self.assertEqual(
            result["cycles_run"],
            3,
        )

    def test_context_provider_is_used(
        self,
    ) -> None:

        controller = MagicMock()
        controller.run_generation_cycle.return_value = {
            "success": True,
            "status": "NO_TASKS",
        }

        runtime = AutoDevRuntime(
            controller=controller,
            context_provider=lambda _: {
                "mode": "file"
            },
        )

        runtime.run_once()

        controller.run_generation_cycle.assert_called_once_with(
            context={
                "mode": "file"
            }
        )


if __name__ == "__main__":
    unittest.main()

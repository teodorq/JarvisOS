import unittest
from unittest.mock import MagicMock

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
    AutonomousDevControllerPolicy,
)


class TestAutonomousDevControllerHealth(unittest.TestCase):

    def _controller(self, pipeline_status):
        pipeline = MagicMock()
        pipeline.status.return_value = pipeline_status
        pipeline.list_tasks.return_value = []

        planner = MagicMock()
        planner.status.return_value = {}

        return AutonomousDevController(
            policy=AutonomousDevControllerPolicy(
                auto_start_pipeline=False,
            ),
            pipeline=pipeline,
            planner=planner,
        )

    def test_health_report_is_healthy(self):
        controller = self._controller({
            "state": "running",
            "last_error": None,
            "queue_metrics": {
                "failed": 0,
                "blocked": 0,
            },
            "scheduler_metrics": {
                "worker_errors": 0,
            },
            "workers": [{"enabled": True}],
        })

        result = controller.handle("autonomous dev health")

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "HEALTHY")
        self.assertEqual(result["workers_enabled"], 1)

    def test_health_report_detects_failed_pipeline(self):
        controller = self._controller({
            "state": "failed",
            "last_error": "boom",
            "queue_metrics": {},
            "scheduler_metrics": {},
            "workers": [{"enabled": True}],
        })

        result = controller.health_report()

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "FAILED")
        self.assertTrue(result["issues"])

    def test_health_report_warns_about_task_errors(self):
        controller = self._controller({
            "state": "running",
            "last_error": None,
            "queue_metrics": {
                "failed": 2,
                "blocked": 1,
            },
            "scheduler_metrics": {
                "worker_errors": 3,
            },
            "workers": [{"enabled": True}],
        })

        result = controller.health_report()

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "DEGRADED")
        self.assertEqual(len(result["warnings"]), 3)

    def test_policy_rejects_invalid_backlog_limit(self):
        with self.assertRaises(ValueError):
            self._controller_with_policy(
                AutonomousDevControllerPolicy(
                    max_backlog_size=0,
                )
            )

    @staticmethod
    def _controller_with_policy(policy):
        return AutonomousDevController(
            policy=policy,
            pipeline=MagicMock(),
            planner=MagicMock(),
        )


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from app.autodev.autodev_scheduler import (
    AutoDevScheduler,
    DispatchDecision,
    SchedulerPolicy,
    SchedulerState,
)
from app.autodev.autonomous_task_queue import (
    AutonomousTaskQueue,
    RetryPolicy,
    TaskStatus,
)


class TestAutoDevSchedulerRetryMetrics(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.queue = AutonomousTaskQueue(
            storage_path=Path(self.temp_dir.name) / "queue.json",
            autosave=True,
        )
        self.scheduler = AutoDevScheduler(
            self.queue,
            policy=SchedulerPolicy(
                poll_interval_seconds=0.01,
                idle_backoff_seconds=0.01,
                max_parallel_tasks=1,
                stale_task_timeout_seconds=30.0,
            ),
        )
        self.scheduler._state = SchedulerState.RUNNING

    def tearDown(self) -> None:
        self.scheduler.stop(wait=True, timeout=1.0)
        self.temp_dir.cleanup()

    def test_submit_task_passes_retry_policy_to_queue(self) -> None:
        retry_policy = RetryPolicy(
            max_attempts=5,
            initial_delay_seconds=0.0,
            backoff_multiplier=1.0,
            max_delay_seconds=0.0,
        )

        task = self.scheduler.submit_task(
            "Retry-aware task",
            "Scheduler must preserve the supplied retry policy",
            retry_policy=retry_policy,
        )

        self.assertEqual(task.retry_policy.max_attempts, 5)
        self.assertEqual(task.retry_policy.initial_delay_seconds, 0.0)

    def test_retry_is_not_counted_as_terminal_failure(self) -> None:
        def failing_handler(task):
            raise RuntimeError("temporary failure")

        self.scheduler.register_worker("worker", failing_handler)
        task = self.scheduler.submit_task(
            "Temporary failure",
            "The first failure should schedule a retry",
            retry_policy=RetryPolicy(
                max_attempts=2,
                initial_delay_seconds=60.0,
                backoff_multiplier=1.0,
                max_delay_seconds=60.0,
            ),
        )

        self.assertEqual(
            self.scheduler.dispatch_once(),
            DispatchDecision.DISPATCHED,
        )
        self.assertTrue(
            self.scheduler.wait_for_active_tasks(timeout=1.0)
        )

        stored = self.queue.require(task.task_id)
        metrics = self.scheduler.metrics()

        self.assertEqual(stored.status, TaskStatus.RETRY_WAIT)
        self.assertEqual(metrics.retried_tasks, 1)
        self.assertEqual(metrics.failed_tasks, 0)
        self.assertEqual(metrics.worker_errors, 1)

    def test_exhausted_retry_is_counted_as_failure(self) -> None:
        def failing_handler(task):
            raise RuntimeError("permanent failure")

        self.scheduler.register_worker("worker", failing_handler)
        task = self.scheduler.submit_task(
            "Permanent failure",
            "No retry should be scheduled",
            retry_policy=RetryPolicy(max_attempts=1),
        )

        self.assertEqual(
            self.scheduler.dispatch_once(),
            DispatchDecision.DISPATCHED,
        )
        self.assertTrue(
            self.scheduler.wait_for_active_tasks(timeout=1.0)
        )

        stored = self.queue.require(task.task_id)
        metrics = self.scheduler.metrics()

        self.assertEqual(stored.status, TaskStatus.FAILED)
        self.assertEqual(metrics.retried_tasks, 0)
        self.assertEqual(metrics.failed_tasks, 1)
        self.assertEqual(metrics.worker_errors, 1)


if __name__ == "__main__":
    unittest.main()

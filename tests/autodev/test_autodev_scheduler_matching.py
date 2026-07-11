import tempfile
import time
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
    TaskStatus,
)


class TestAutoDevSchedulerWorkerMatching(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.queue = AutonomousTaskQueue(
            storage_path=(
                Path(self.temp_dir.name) / "scheduler_queue.json"
            ),
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

    def test_dispatch_uses_later_compatible_worker(self) -> None:
        handled_by = []

        self.scheduler.register_worker(
            "worker-a",
            lambda task: handled_by.append("worker-a"),
            accepted_sources={"source-a"},
        )
        self.scheduler.register_worker(
            "worker-b",
            lambda task: handled_by.append("worker-b"),
            accepted_sources={"source-b"},
        )

        task = self.queue.create_task(
            title="Compatible worker task",
            description="Must be handled by worker-b",
            source="source-b",
        )

        decision = self.scheduler.dispatch_once()

        self.assertEqual(decision, DispatchDecision.DISPATCHED)
        self.assertTrue(
            self.scheduler.wait_for_active_tasks(timeout=1.0)
        )
        self.assertEqual(handled_by, ["worker-b"])
        self.assertEqual(
            self.queue.require(task.task_id).status,
            TaskStatus.COMPLETED,
        )

    def test_no_task_when_no_worker_matches(self) -> None:
        self.scheduler.register_worker(
            "worker-a",
            lambda task: {"ok": True},
            accepted_sources={"source-a"},
        )
        task = self.queue.create_task(
            title="Unmatched task",
            description="No registered worker accepts it",
            source="source-b",
        )

        decision = self.scheduler.dispatch_once()

        self.assertEqual(decision, DispatchDecision.NO_TASK)
        self.assertEqual(
            self.queue.require(task.task_id).status,
            TaskStatus.READY,
        )

    def test_busy_worker_is_skipped_for_compatible_worker(self) -> None:
        handled_by = []

        busy_worker = self.scheduler.register_worker(
            "worker-a",
            lambda task: handled_by.append("worker-a"),
            accepted_sources={"shared"},
        )
        busy_worker.busy = True

        self.scheduler.register_worker(
            "worker-b",
            lambda task: handled_by.append("worker-b"),
            accepted_sources={"shared"},
        )

        self.queue.create_task(
            title="Shared source task",
            description="Use an available compatible worker",
            source="shared",
        )

        decision = self.scheduler.dispatch_once()

        self.assertEqual(decision, DispatchDecision.DISPATCHED)
        self.assertTrue(
            self.scheduler.wait_for_active_tasks(timeout=1.0)
        )
        self.assertEqual(handled_by, ["worker-b"])


if __name__ == "__main__":
    unittest.main()

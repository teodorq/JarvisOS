import tempfile
import unittest
from pathlib import Path

from app.autodev.autodev_pipeline import (
    AutoDevPipeline,
    AutoDevPipelinePolicy,
)
from app.autodev.autonomous_task_queue import (
    AutonomousTaskQueue,
    TaskPriority,
    TaskStatus,
)
from app.autodev.pipeline_events import (
    PipelineEventBus,
    PipelineEventType,
)
from app.autodev.pipeline_report import PipelineReport


class TestAutoDevPipeline(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.queue_path = self.root / "queue.json"

        self.queue = AutonomousTaskQueue(
            storage_path=self.queue_path,
            autosave=True,
        )

        self.policy = AutoDevPipelinePolicy(
            project_root=str(self.root),
            queue_storage_path=str(self.queue_path),
            worker_count=1,
            auto_approve=False,
            auto_execute=False,
            auto_rollback=True,
            max_parallel_tasks=1,
        )

        self.pipeline = AutoDevPipeline(
            policy=self.policy,
            queue=self.queue,
        )

    def tearDown(self) -> None:
        try:
            self.pipeline.stop(wait=False)
        except Exception:
            pass

        self.temp_dir.cleanup()

    def test_submit_creates_task(self) -> None:
        task = self.pipeline.submit(
            title="Test task",
            description="Test description",
            source="unit_test",
            priority=TaskPriority.HIGH,
            payload={
                "goal": "Test description",
                "target": "Test",
                "mode": "file",
                "path": "sample.py",
                "proposed_content": "print('ok')\n",
            },
        )

        self.assertEqual(task.title, "Test task")
        self.assertEqual(task.source, "unit_test")
        self.assertIn(
            task.status,
            {
                TaskStatus.PENDING,
                TaskStatus.READY,
            },
        )

    def test_list_tasks_returns_serialized_tasks(self) -> None:
        self.pipeline.submit(
            title="List task",
            description="List test",
            payload={
                "goal": "List test",
                "target": "List",
                "mode": "file",
                "path": "list_test.py",
                "proposed_content": "value = 1\n",
            },
        )

        tasks = self.pipeline.list_tasks()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "List task")

    def test_cancel_task(self) -> None:
        task = self.pipeline.submit(
            title="Cancel task",
            description="Cancel test",
            payload={
                "goal": "Cancel test",
                "target": "Cancel",
                "mode": "file",
                "path": "cancel_test.py",
                "proposed_content": "value = 2\n",
            },
        )

        cancelled = self.pipeline.cancel_task(task.task_id)

        self.assertEqual(
            cancelled.status,
            TaskStatus.CANCELLED,
        )

    def test_report_contains_pipeline_sections(self) -> None:
        report = PipelineReport().build(self.pipeline)

        self.assertIn("AUTODEV PIPELINE REPORT", report)
        self.assertIn("QUEUE", report)
        self.assertIn("SCHEDULER", report)
        self.assertIn("WORKERS", report)


class TestPipelineEvents(unittest.TestCase):

    def test_event_bus_publishes_and_stores_event(self) -> None:
        bus = PipelineEventBus()
        received = []

        bus.subscribe(received.append)

        event = bus.emit(
            PipelineEventType.TASK_ENQUEUED,
            source="unit_test",
            task_id="task-1",
            message="Task queued",
        )

        self.assertEqual(len(received), 1)
        self.assertEqual(
            received[0].event_type,
            PipelineEventType.TASK_ENQUEUED,
        )
        self.assertEqual(
            bus.history()[0]["task_id"],
            "task-1",
        )
        self.assertEqual(
            event.message,
            "Task queued",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.autonomous_dev_controller import (
    AutonomousDevController,
)
from app.autodev.autodev_pipeline import AutoDevPipeline
from app.autodev.autodev_worker import (
    AutoDevWorker,
    WorkerState,
)
from app.autodev.error_reporting import (
    AutoDevErrorReporter,
)
from app.autodev.execution_result import ExecutionResult
from app.autodev.workflow_result import WorkflowResult


class AuditA42ErrorHandlingTests(unittest.TestCase):

    def test_report_redacts_secrets_and_project_root(self) -> None:
        report = AutoDevErrorReporter.capture(
            RuntimeError(
                "token=abc123 "
                "C:/JarvisAI/app/demo.py"
            ),
            stage="worker.execute",
            context={
                "password": "secret-value",
                "path": "C:/JarvisAI/app/demo.py",
            },
            project_root="C:/JarvisAI",
        )
        payload = report.as_dict()

        self.assertNotIn(
            "abc123",
            payload["message"],
        )
        self.assertNotIn(
            "C:/JarvisAI",
            payload["message"],
        )
        self.assertEqual(
            payload["context"]["password"],
            "<REDACTED>",
        )
        self.assertIn(
            "<PROJECT_ROOT>",
            payload["context"]["path"],
        )

    def test_retryability_is_classified(self) -> None:
        self.assertTrue(
            AutoDevErrorReporter.capture(
                TimeoutError("timeout"),
                stage="test",
            ).retryable
        )
        self.assertFalse(
            AutoDevErrorReporter.capture(
                ValueError("bad input"),
                stage="test",
            ).retryable
        )

    def test_execution_result_accepts_structured_exception(
        self,
    ) -> None:
        result = ExecutionResult(
            success=True,
            step_name="validate",
            message="running",
        )

        details = result.add_exception(
            ValueError("bad token=private"),
            project_root="C:/JarvisAI",
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error_details[0],
            details,
        )
        self.assertNotIn(
            "private",
            result.errors[0],
        )
        self.assertIn(
            "error_details",
            result.as_dict(),
        )

    def test_workflow_result_accepts_structured_exception(
        self,
    ) -> None:
        result = WorkflowResult(
            success=True,
            status="executing",
            message="running",
        )

        result.add_exception(
            TimeoutError("temporary"),
            stage="workflow.execute",
        )

        self.assertFalse(result.success)
        self.assertTrue(
            result.error_details[0][
                "retryable"
            ]
        )
        self.assertIn(
            "error_details",
            result.as_dict(),
        )

    def test_worker_exception_has_safe_error_envelope(
        self,
    ) -> None:
        worker = AutoDevWorker.__new__(
            AutoDevWorker
        )
        worker.worker_id = "worker-1"
        worker.policy = SimpleNamespace(
            project_root="C:/JarvisAI",
        )
        worker._lock = threading.RLock()
        worker._state = WorkerState.IDLE
        worker._current_task_id = None
        worker._last_result = None
        worker._build_request = MagicMock(
            side_effect=RuntimeError(
                "password=hunter2 "
                "C:/JarvisAI/app/demo.py"
            )
        )
        task = SimpleNamespace(
            task_id="task-1",
        )

        result = worker.execute(task)

        self.assertEqual(
            result.status,
            "worker_exception",
        )
        self.assertTrue(
            result.error_details,
        )
        self.assertEqual(
            result.data["error_id"],
            result.error_details[0][
                "error_id"
            ],
        )
        self.assertNotIn(
            "hunter2",
            result.errors[0],
        )
        self.assertNotIn(
            "C:/JarvisAI",
            result.errors[0],
        )

    def test_pipeline_keeps_structured_last_error(
        self,
    ) -> None:
        pipeline = AutoDevPipeline.__new__(
            AutoDevPipeline
        )
        pipeline._lock = threading.RLock()
        pipeline._last_error = None
        pipeline._last_error_info = None
        pipeline._started_at = None
        pipeline.policy = SimpleNamespace(
            project_root="C:/JarvisAI",
        )
        pipeline.scheduler = MagicMock()
        pipeline.scheduler.state.value = "stopped"
        pipeline.scheduler.start.side_effect = TimeoutError(
            "token=hidden"
        )

        with self.assertRaises(
            TimeoutError
        ):
            pipeline.start()

        self.assertTrue(
            pipeline.last_error
        )
        self.assertTrue(
            pipeline.last_error_info[
                "retryable"
            ]
        )
        self.assertNotIn(
            "hidden",
            pipeline.last_error,
        )

    def test_invalid_priority_reports_allowed_values(
        self,
    ) -> None:
        controller = (
            AutonomousDevController.__new__(
                AutonomousDevController
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Dozwolone wartości",
        ):
            controller.calculate_priority(
                goal="demo",
                context={
                    "priority": "impossible",
                },
            )

    def test_error_report_contains_no_traceback(
        self,
    ) -> None:
        try:
            raise RuntimeError("boom")
        except RuntimeError as error:
            report = AutoDevErrorReporter.capture(
                error,
                stage="test",
            )

        payload = str(
            report.as_dict()
        ).casefold()

        self.assertNotIn(
            "traceback",
            payload,
        )
        self.assertNotIn(
            "file \"",
            payload,
        )


if __name__ == "__main__":
    unittest.main()

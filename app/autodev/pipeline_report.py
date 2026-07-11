from __future__ import annotations

from datetime import datetime
from typing import Any


class PipelineReport:
    def build(
        self,
        pipeline: Any,
    ) -> str:
        status = pipeline.status()
        queue = status.get("queue_metrics", {})
        scheduler = status.get("scheduler_metrics", {})
        workers = status.get("workers", [])

        lines = [
            "AUTODEV PIPELINE REPORT",
            "",
            f"Generated: {datetime.now().isoformat()}",
            f"State: {status.get('state', 'unknown')}",
            f"Started at: {status.get('started_at')}",
            f"Last error: {status.get('last_error') or 'none'}",
            "",
            "QUEUE",
            f"Total: {queue.get('total', 0)}",
            f"Pending: {queue.get('pending', 0)}",
            f"Ready: {queue.get('ready', 0)}",
            f"Running: {queue.get('running', 0)}",
            f"Retry wait: {queue.get('retry_wait', 0)}",
            f"Blocked: {queue.get('blocked', 0)}",
            f"Completed: {queue.get('completed', 0)}",
            f"Failed: {queue.get('failed', 0)}",
            f"Cancelled: {queue.get('cancelled', 0)}",
            "",
            "SCHEDULER",
            (
                "Dispatch attempts: "
                f"{scheduler.get('dispatch_attempts', 0)}"
            ),
            (
                "Dispatched tasks: "
                f"{scheduler.get('dispatched_tasks', 0)}"
            ),
            (
                "Completed tasks: "
                f"{scheduler.get('completed_tasks', 0)}"
            ),
            (
                "Failed tasks: "
                f"{scheduler.get('failed_tasks', 0)}"
            ),
            (
                "Active tasks: "
                f"{scheduler.get('active_tasks', 0)}"
            ),
            (
                "Registered workers: "
                f"{scheduler.get('registered_workers', 0)}"
            ),
            "",
            "WORKERS",
        ]

        if not workers:
            lines.append("No workers registered.")
        else:
            for worker in workers:
                lines.extend(
                    [
                        (
                            f"- {worker.get('worker_id', 'unknown')}"
                        ),
                        (
                            f"  State: "
                            f"{worker.get('state', 'unknown')}"
                        ),
                        (
                            f"  Current task: "
                            f"{worker.get('current_task_id') or 'none'}"
                        ),
                    ]
                )

        return "\n".join(lines)

    def build_dict(
        self,
        pipeline: Any,
    ) -> dict[str, Any]:
        return {
            "report": self.build(pipeline),
            "status": pipeline.status(),
            "snapshot": pipeline.snapshot(),
        }

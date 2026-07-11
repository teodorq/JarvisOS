from __future__ import annotations

import threading
import time

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class PipelineMetricsSnapshot:
    timestamp: float
    queue_total: int
    queue_ready: int
    queue_running: int
    queue_completed: int
    queue_failed: int
    queue_cancelled: int
    scheduler_active_tasks: int
    scheduler_registered_workers: int
    scheduler_dispatched_tasks: int
    scheduler_completed_tasks: int
    scheduler_failed_tasks: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PipelineMetricsCollector:
    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline
        self._history: list[PipelineMetricsSnapshot] = []
        self._lock = threading.RLock()

    def collect(self) -> PipelineMetricsSnapshot:
        queue_metrics = self.pipeline.queue.metrics()
        scheduler_metrics = self.pipeline.scheduler.metrics()

        snapshot = PipelineMetricsSnapshot(
            timestamp=time.time(),
            queue_total=queue_metrics.total,
            queue_ready=queue_metrics.ready,
            queue_running=queue_metrics.running,
            queue_completed=queue_metrics.completed,
            queue_failed=queue_metrics.failed,
            queue_cancelled=queue_metrics.cancelled,
            scheduler_active_tasks=(
                scheduler_metrics.active_tasks
            ),
            scheduler_registered_workers=(
                scheduler_metrics.registered_workers
            ),
            scheduler_dispatched_tasks=(
                scheduler_metrics.dispatched_tasks
            ),
            scheduler_completed_tasks=(
                scheduler_metrics.completed_tasks
            ),
            scheduler_failed_tasks=(
                scheduler_metrics.failed_tasks
            ),
        )

        with self._lock:
            self._history.append(snapshot)

        return snapshot

    def latest(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._history:
                return None

            return self._history[-1].to_dict()

    def history(
        self,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history)

        if limit is not None:
            items = items[-max(0, limit):]

        return [
            item.to_dict()
            for item in items
        ]

    def summary(self) -> dict[str, Any]:
        latest = self.latest()

        if latest is None:
            latest = self.collect().to_dict()

        success_total = (
            latest["scheduler_completed_tasks"]
            + latest["scheduler_failed_tasks"]
        )

        success_rate = (
            latest["scheduler_completed_tasks"]
            / success_total
            if success_total
            else 0.0
        )

        return {
            "latest": latest,
            "success_rate": success_rate,
            "samples": len(self._history),
        }

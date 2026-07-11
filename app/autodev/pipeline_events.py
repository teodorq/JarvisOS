from __future__ import annotations

import threading
import time

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable


class PipelineEventType(StrEnum):
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_STOPPED = "pipeline_stopped"
    PIPELINE_PAUSED = "pipeline_paused"
    PIPELINE_RESUMED = "pipeline_resumed"
    TASK_ENQUEUED = "task_enqueued"
    TASK_CLAIMED = "task_claimed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    TASK_RETRY_SCHEDULED = "task_retry_scheduled"
    WORKER_REGISTERED = "worker_registered"
    WORKER_ERROR = "worker_error"


@dataclass(slots=True)
class PipelineEvent:
    event_type: PipelineEventType
    source: str
    message: str = ""
    task_id: str | None = None
    worker_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event_type"] = self.event_type.value
        return payload


class PipelineEventBus:
    def __init__(self, *, history_limit: int = 1000) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be at least 1")

        self.history_limit = history_limit
        self._listeners: list[
            Callable[[PipelineEvent], None]
        ] = []
        self._history: list[PipelineEvent] = []
        self._lock = threading.RLock()

    def subscribe(
        self,
        listener: Callable[[PipelineEvent], None],
    ) -> None:
        if not callable(listener):
            raise TypeError("listener must be callable")

        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(
        self,
        listener: Callable[[PipelineEvent], None],
    ) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def publish(
        self,
        event: PipelineEvent,
    ) -> None:
        with self._lock:
            self._history.append(event)

            if len(self._history) > self.history_limit:
                self._history = self._history[
                    -self.history_limit:
                ]

            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(event)
            except Exception:
                continue

    def emit(
        self,
        event_type: PipelineEventType,
        *,
        source: str,
        message: str = "",
        task_id: str | None = None,
        worker_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> PipelineEvent:
        event = PipelineEvent(
            event_type=event_type,
            source=source,
            message=message,
            task_id=task_id,
            worker_id=worker_id,
            data=dict(data or {}),
        )
        self.publish(event)
        return event

    def history(
        self,
        *,
        event_type: PipelineEventType | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._history)

        if event_type is not None:
            events = [
                event
                for event in events
                if event.event_type == event_type
            ]

        events.sort(
            key=lambda event: event.created_at,
            reverse=True,
        )

        if limit is not None:
            events = events[:max(0, limit)]

        return [
            event.to_dict()
            for event in events
        ]

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

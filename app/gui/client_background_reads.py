from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
)


class _ReadSignals(QObject):
    done = Signal(object, object)
    failed = Signal(object, object)


class _ReadJob(QRunnable):
    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _ReadSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self, self.operation())
        except Exception as error:
            self.signals.failed.emit(self, error)


class ClientBackgroundReadRuntime(QObject):
    """One non-blocking lane for proactive client reads."""

    def __init__(self, window: QObject) -> None:
        super().__init__(window)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._active: _ReadJob | None = None
        self._done: Callable[[Any], None] | None = None
        self._failed: Callable[[object], None] | None = None
        self._closed = False

    def submit(
        self,
        operation: Callable[[], Any],
        done: Callable[[Any], None],
        failed: Callable[[object], None],
    ) -> bool:
        if self._closed or self._active is not None:
            return False
        job = _ReadJob(operation)
        self._active, self._done, self._failed = job, done, failed
        job.signals.done.connect(self._complete)
        job.signals.failed.connect(self._failure)
        self.pool.start(job)
        return True

    def shutdown(self) -> None:
        self._closed = True
        job = self._active
        if job is not None and self.pool.tryTake(job):
            self._clear(job)

    @Slot(object, object)
    def _complete(self, job: _ReadJob, result: Any) -> None:
        callback = self._done
        self._clear(job)
        if not self._closed and callback is not None:
            callback(result)

    @Slot(object, object)
    def _failure(self, job: _ReadJob, error: object) -> None:
        callback = self._failed
        self._clear(job)
        if not self._closed and callback is not None:
            callback(error)

    def _clear(self, job: _ReadJob) -> None:
        if self._active is job:
            self._active = None
            self._done = None
            self._failed = None


def submit_client_read(
    window: Any,
    operation: Callable[[], Any],
    done: Callable[[Any], None],
    failed: Callable[[object], None],
) -> bool:
    """Use the GUI thread only for callbacks; keep I/O in the worker pool."""
    if not isinstance(window, QObject) or QCoreApplication.instance() is None:
        try:
            done(operation())
        except Exception as error:
            failed(error)
        return True
    runtime = getattr(window, "_client_background_reads", None)
    if runtime is None:
        runtime = ClientBackgroundReadRuntime(window)
        window._client_background_reads = runtime
    return runtime.submit(operation, done, failed)

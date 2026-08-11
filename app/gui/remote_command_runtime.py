from __future__ import annotations

import os
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from app.cloud.client import CloudPlannerClient

class _RemoteSignals(QObject):
    done = Signal(object, object)
    failed = Signal(object, object)

class _RemoteJob(QRunnable):
    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = _RemoteSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self, self.function())
        except Exception as error:
            self.signals.failed.emit(self, error)

class RemoteCommandRuntime(QObject):
    """Polls the relay without blocking Qt and preserves local confirmation."""

    TERMINAL_STATES = {"completed", "failed", "cancelled"}

    def __init__(self, window: Any, client: CloudPlannerClient | None = None) -> None:
        super().__init__(window)
        self.window = window
        self.client = client or CloudPlannerClient()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.timer = QTimer(self)
        self.timer.setInterval(_poll_interval_ms())
        self.timer.timeout.connect(self.poll)
        self._job: _RemoteJob | None = None
        self._callback: Callable[[Any], None] | None = None
        self._active_id = ""
        self._pending_report: tuple[str, str, bool] | None = None
        self._closed = False
        signal = getattr(window, "client_event_signal", None)
        if signal is not None:
            signal.connect(self._on_client_event)

    def start(self) -> None:
        if not self.client.remote_enabled or self._closed:
            return
        self.timer.start()
        QTimer.singleShot(1200, self.poll)

    def shutdown(self) -> None:
        self._closed = True
        self.timer.stop()
        self._callback = None
        self.pool.clear()
        self.pool.waitForDone(1200)

    def poll(self) -> None:
        if self._closed or not self.client.remote_enabled or self._job is not None:
            return
        if self._pending_report is not None:
            self._flush_report()
            return
        if self._active_id or self._window_busy():
            return
        self._submit(self.client.claim_remote_command, self._after_claim)

    def _window_busy(self) -> bool:
        if getattr(self.window, "pending_thought", None) is not None:
            return True
        client_runtime = getattr(self.window, "_client_background_commands", None)
        if client_runtime is not None and bool(getattr(client_runtime, "_jobs", set())):
            return True
        owner_runtime = getattr(self.window, "_owner_background_commands", None)
        return bool(owner_runtime is not None and getattr(owner_runtime, "busy", False))

    def _after_claim(self, record: object) -> None:
        if not isinstance(record, dict) or not record:
            return
        command_id = str(record.get("id", ""))
        command = str(record.get("command", "")).strip()
        kind = str(record.get("kind", "command")).strip().lower()
        if len(command_id) != 32 or not command:
            return
        self._active_id = command_id
        if kind == "probe":
            self._queue_report("completed", "Komputer jest online.", True)
            return
        try:
            self.window.process_client_command(command)
        except Exception:
            self._queue_report("failed", "Nie uda\u0142o si\u0119 rozpocz\u0105\u0107 polecenia na komputerze.", True)

    def _on_client_event(self, raw_event: object) -> None:
        if not self._active_id or not isinstance(raw_event, dict):
            return
        state = str(raw_event.get("state", "")).strip().lower()
        message = " ".join(str(raw_event.get("message", "")).split())
        if bool(raw_event.get("requires_confirmation", False)):
            self._queue_report(
                "waiting_local_confirmation",
                message or "Polecenie czeka na potwierdzenie na komputerze.",
                False,
            )
        elif state == "success":
            self._queue_report("completed", message or "Zadanie zako\u0144czone.", True)
        elif state == "error":
            self._queue_report("failed", message or "Zadanie nie powiod\u0142o si\u0119.", True)
        elif state == "idle" and "anul" in message.casefold():
            self._queue_report("cancelled", message or "Zadanie anulowane.", True)

    def _queue_report(self, status: str, message: str, terminal: bool) -> None:
        pending = self._pending_report
        if pending is None or terminal or not pending[2]:
            self._pending_report = (status, message[:2_000], terminal)
        if self._job is None:
            self._flush_report()

    def _flush_report(self) -> None:
        if not self._active_id or self._pending_report is None or self._job is not None:
            return
        status, message, terminal = self._pending_report
        command_id = self._active_id
        self._pending_report = None
        self._submit(
            lambda: self.client.report_remote_command(command_id, status, message),
            lambda _result: self._after_report(command_id, terminal),
            lambda _error: self._report_failed(status, message, terminal),
        )

    def _after_report(self, command_id: str, terminal: bool) -> None:
        if terminal and command_id == self._active_id:
            self._active_id = ""
        if self._pending_report is not None:
            QTimer.singleShot(0, self._flush_report)

    def _report_failed(self, status: str, message: str, terminal: bool) -> None:
        self._pending_report = (status, message, terminal)
        QTimer.singleShot(min(self.timer.interval(), 10_000), self.poll)

    def _submit(
        self,
        function: Callable[[], Any],
        callback: Callable[[Any], None],
        failed: Callable[[Any], None] | None = None,
    ) -> None:
        job = _RemoteJob(function)
        self._job = job
        self._callback = callback
        job.signals.done.connect(self._complete)
        job.signals.failed.connect(
            lambda finished, error: self._failed(finished, error, failed)
        )
        self.pool.start(job)

    @Slot(object, object)
    def _complete(self, job: _RemoteJob, result: Any) -> None:
        if job is not self._job:
            return
        callback = self._callback
        self._job = None
        self._callback = None
        if not self._closed and callable(callback):
            callback(result)

    def _failed(self, job: _RemoteJob, error: object, callback) -> None:
        if job is not self._job:
            return
        self._job = None
        self._callback = None
        if not self._closed and callable(callback):
            callback(error)

def _poll_interval_ms() -> int:
    value = os.getenv("JARVIS_OS_REMOTE_POLL_SECONDS", "5").strip()
    try:
        seconds = float(value)
    except ValueError:
        seconds = 5.0
    return int(min(max(seconds, 3.0), 60.0) * 1000)

def connect_remote_command_runtime(window: Any) -> None:
    if hasattr(window, "_remote_command_runtime"):
        return
    runtime = RemoteCommandRuntime(window)
    window._remote_command_runtime = runtime
    runtime.start()

def shutdown_remote_command_runtime(window: Any) -> None:
    runtime = getattr(window, "_remote_command_runtime", None)
    if runtime is not None:
        runtime.shutdown()

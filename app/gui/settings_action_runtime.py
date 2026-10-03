from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.core.runtime_maintenance import (
    cleanup_runtime_storage,
    runtime_storage_status,
)
from app.gui.settings_page_extensions import (
    set_settings_action_busy,
    set_settings_action_feedback,
)


class _Signals(QObject):
    done = Signal(object, object)
    failed = Signal(object, object)


class _Job(QRunnable):
    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.done.emit(self, self.operation())
        except Exception as error:
            self.signals.failed.emit(self, error)


class SettingsActionRuntime(QObject):
    """Dedicated settings worker so disk inspection never freezes the UI."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.page = window.settings_page
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._active: _Job | None = None

    def check_health(self) -> None:
        self._submit(
            lambda: runtime_storage_status(self.window.project_root),
            self._health_text,
        )

    def cleanup(self) -> None:
        self._submit(
            lambda: cleanup_runtime_storage(self.window.project_root),
            self._cleanup_text,
        )

    def _submit(
        self,
        operation: Callable[[], Any],
        formatter: Callable[[dict[str, Any]], str],
    ) -> None:
        if self._active is not None:
            return
        set_settings_action_busy(self.page, True)
        job = _Job(operation)
        self._active = job
        job.signals.done.connect(
            lambda current, result: self._complete(current, result, formatter)
        )
        job.signals.failed.connect(self._failed)
        self.pool.start(job)

    def _complete(
        self,
        job: _Job,
        result: object,
        formatter: Callable[[dict[str, Any]], str],
    ) -> None:
        if self._active is not job:
            return
        self._active = None
        payload = dict(result) if isinstance(result, dict) else {}
        set_settings_action_feedback(self.page, formatter(payload), True)

    @Slot(object, object)
    def _failed(self, job: _Job, _error: object) -> None:
        if self._active is not job:
            return
        self._active = None
        set_settings_action_feedback(
            self.page,
            "Nie udało się zakończyć kontroli. Dane pozostały bez zmian.",
            False,
        )

    @staticmethod
    def _health_text(value: dict[str, Any]) -> str:
        profile = {
            "low_resource": "oszczędny",
            "balanced": "pełna jakość",
        }.get(str(value.get("profile", "")), "automatyczny")
        return (
            f"Stan prawidłowy • tryb {profile} • dane "
            f"{_size(value.get('data_bytes', 0))} • wolne na dysku "
            f"{_size(value.get('disk_free_bytes', 0))}."
        )

    @staticmethod
    def _cleanup_text(value: dict[str, Any]) -> str:
        return (
            f"Porządkowanie zakończone • odzyskano "
            f"{_size(value.get('saved_bytes', 0))} • usunięte stare zrzuty: "
            f"{int(value.get('removed_screenshots', 0) or 0)}."
        )


def _size(value: object) -> str:
    amount = max(0, int(value or 0))
    if amount >= 1024**3:
        return f"{amount / 1024**3:.1f} GB"
    if amount >= 1024**2:
        return f"{amount / 1024**2:.1f} MB"
    return f"{amount / 1024:.1f} KB"


def connect_settings_actions(window: Any) -> SettingsActionRuntime:
    runtime = SettingsActionRuntime(window)
    window.settings_page.health_requested.connect(runtime.check_health)
    window.settings_page.cleanup_requested.connect(runtime.cleanup)
    window._settings_action_runtime = runtime
    return runtime


__all__ = ["SettingsActionRuntime", "connect_settings_actions"]

from __future__ import annotations

import threading
from typing import Any

from app.autodev.autonomous_executor import AutonomousExecutor


class AutonomousService:
    """
    Runs the autonomous loop in a background thread.

    The service is intentionally conservative:
    - only one background run can exist,
    - stop requests are forwarded to the manager,
    - the last result and last error are retained.
    """

    def __init__(
        self,
        executor: AutonomousExecutor | None = None,
    ) -> None:
        self.executor = executor or AutonomousExecutor()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._last_result: dict[str, Any] | None = None
        self._last_error: str | None = None

    def start(
        self,
        *,
        max_cycles: int | None = None,
        context: dict[str, Any] | None = None,
        background: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return {
                    "success": True,
                    "status": "ALREADY_RUNNING",
                }

            if not background:
                try:
                    result = self.executor.start(
                        max_cycles=max_cycles,
                        context=context,
                    )
                    self._last_result = dict(result)
                    self._last_error = None
                    return result
                except Exception as error:
                    self._last_error = (
                        f"{type(error).__name__}: {error}"
                    )
                    return {
                        "success": False,
                        "status": "FAILED",
                        "error": self._last_error,
                    }

            self._thread = threading.Thread(
                target=self._run_background,
                kwargs={
                    "max_cycles": max_cycles,
                    "context": dict(context or {}),
                },
                name="jarvis-autonomous-service",
                daemon=True,
            )
            self._thread.start()

            return {
                "success": True,
                "status": "STARTED",
                "background": True,
            }

    def _run_background(
        self,
        *,
        max_cycles: int | None,
        context: dict[str, Any],
    ) -> None:
        try:
            result = self.executor.start(
                max_cycles=max_cycles,
                context=context,
            )
            with self._lock:
                self._last_result = dict(result)
                self._last_error = None
        except Exception as error:
            with self._lock:
                self._last_error = (
                    f"{type(error).__name__}: {error}"
                )

    def stop(self) -> dict[str, Any]:
        result = self.executor.stop()
        return {
            **dict(result),
            "service_running": self.is_running(),
        }

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "RUNNING" if self.is_running() else "STOPPED",
            "running": self.is_running(),
            "last_result": self._last_result,
            "last_error": self._last_error,
            "executor": self.executor.status(),
        }

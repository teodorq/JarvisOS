from __future__ import annotations

import threading
import time
from typing import Any

from app.autodev.background_worker import BackgroundWorker


class BackgroundAutonomyService:

    def __init__(
        self,
        worker: BackgroundWorker | None = None,
    ) -> None:
        self.worker = worker or BackgroundWorker()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return {
                    "success": True,
                    "status": "ALREADY_RUNNING",
                }

            self.worker.enable()
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="jarvis-background-autodev",
                daemon=True,
            )
            self._thread.start()

            return {
                "success": True,
                "status": "STARTED",
            }

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        worker_result = self.worker.disable()

        return {
            "success": True,
            "status": "STOP_REQUESTED",
            "worker": worker_result,
        }

    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "RUNNING" if self.is_running() else "STOPPED",
            "running": self.is_running(),
            "worker": self.worker.status(),
        }

    def tick(self) -> dict[str, Any]:
        return self.worker.tick()

    def user_activity(self) -> dict[str, Any]:
        return self.worker.on_user_activity()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.worker.tick()

            interval = self.worker.policy.check_interval_seconds
            self._stop_event.wait(timeout=interval)

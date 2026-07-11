from __future__ import annotations

import threading
from typing import Any

from app.autodev.autonomous_improvement_service import (
    AutonomousImprovementService,
)


class AutonomousImprovementBackground:
    """
    Okresowa pętla podglądu autonomicznych ulepszeń.

    Ważne:
    - zawsze wywołuje preview(),
    - nie zatwierdza zmian,
    - nie zapisuje kodu samodzielnie,
    - działa jako bezpieczny monitoring.
    """

    def __init__(
        self,
        service: AutonomousImprovementService,
        interval_seconds: float = 300.0,
    ) -> None:

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds musi być większe od 0."
            )

        self.service = service
        self.interval_seconds = float(
            interval_seconds
        )

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        self.cycles_completed = 0
        self.last_result: dict[str, Any] | None = None
        self.last_error: str | None = None

    def start(
        self,
    ) -> bool:

        with self._lock:
            if self.is_running():
                return False

            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run,
                name=(
                    "AutonomousImprovementBackground"
                ),
                daemon=True,
            )

            self._thread.start()

            return True

    def stop(
        self,
        *,
        wait: bool = True,
        timeout: float | None = 5.0,
    ) -> bool:

        with self._lock:
            if not self.is_running():
                return False

            self._stop_event.set()
            thread = self._thread

        if (
            wait
            and thread is not None
            and thread is not threading.current_thread()
        ):
            thread.join(
                timeout=timeout
            )

        return True

    def run_once(
        self,
    ) -> dict[str, Any]:

        try:
            result = self.service.preview()

            normalized = (
                dict(result)
                if isinstance(
                    result,
                    dict,
                )
                else {
                    "success": False,
                    "status": "INVALID_RESULT",
                }
            )

            with self._lock:
                self.cycles_completed += 1
                self.last_result = normalized
                self.last_error = None

            return dict(
                normalized
            )

        except Exception as error:
            error_text = (
                f"{type(error).__name__}: {error}"
            )

            result = {
                "success": False,
                "status": (
                    "BACKGROUND_PREVIEW_FAILED"
                ),
                "error": error_text,
            }

            with self._lock:
                self.cycles_completed += 1
                self.last_result = result
                self.last_error = error_text

            return dict(
                result
            )

    def is_running(
        self,
    ) -> bool:

        thread = self._thread

        return bool(
            thread is not None
            and thread.is_alive()
            and not self._stop_event.is_set()
        )

    def status(
        self,
    ) -> dict[str, Any]:

        with self._lock:
            return {
                "running": self.is_running(),
                "interval_seconds": (
                    self.interval_seconds
                ),
                "cycles_completed": (
                    self.cycles_completed
                ),
                "last_result": self.last_result,
                "last_error": self.last_error,
            }

    def _run(
        self,
    ) -> None:

        while not self._stop_event.is_set():
            self.run_once()

            if self._stop_event.wait(
                self.interval_seconds
            ):
                break

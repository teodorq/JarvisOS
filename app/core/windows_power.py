"""Bounded Windows shutdown scheduling for the authenticated phone bridge."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import threading
from typing import Any, Callable

from app.cloud.contracts import (
    REMOTE_POWER_CANCEL_KIND,
    REMOTE_POWER_SHUTDOWN_KIND,
)
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


class WindowsPowerController:
    """Schedule one graceful local shutdown without invoking a command shell."""

    def __init__(
        self,
        *,
        delay_seconds: int = 60,
        executable: str | Path | None = None,
        runner: Callable[..., Any] = subprocess.run,
        timer_factory: Callable[[float, Callable[[], None]], Any] = threading.Timer,
        platform_name: str | None = None,
        project_root: str | Path | None = None,
    ) -> None:
        self.delay_seconds = min(max(int(delay_seconds), 30), 300)
        self.executable = Path(executable) if executable else self._system_executable()
        self.runner = runner
        self.timer_factory = timer_factory
        self.platform_name = platform_name or os.name
        self._lock = threading.Lock()
        self._timer: Any | None = None
        self._generation = 0
        self._last_execution = "NEVER"
        root = resolve_project_root(project_root)
        self.processed = JsonStore(
            root / "data" / "system" / "remote_power_requests.json",
            lambda: {"schema_version": 1, "request_ids": []},
        )

    def execute(self, kind: str, request_id: str) -> dict[str, Any]:
        if not self._valid_request_id(request_id):
            return {"ok": False, "message": "Nieprawidłowe polecenie zasilania."}
        if request_id in self._processed_ids():
            return {
                "ok": True,
                "message": "To polecenie zasilania zostało już bezpiecznie obsłużone.",
            }
        if kind == REMOTE_POWER_SHUTDOWN_KIND:
            result = self.schedule_shutdown()
        elif kind == REMOTE_POWER_CANCEL_KIND:
            result = self.cancel_shutdown()
        else:
            return {"ok": False, "message": "Nieobsługiwane polecenie zasilania."}
        if result.get("ok") is True and not self._remember(request_id):
            if kind == REMOTE_POWER_SHUTDOWN_KIND:
                self.cancel_shutdown()
            return {
                "ok": False,
                "message": "Nie zapisałem zabezpieczenia przed powtórzeniem; odliczanie anulowane.",
            }
        return result

    def schedule_shutdown(self) -> dict[str, Any]:
        if self.platform_name != "nt" or not self.executable.is_file():
            return {
                "ok": False,
                "message": "Bezpieczne wyłączenie jest niedostępne na tym komputerze.",
            }
        with self._lock:
            if self._timer is not None:
                return {
                    "ok": True,
                    "message": self._scheduled_message("jest już zaplanowane"),
                }
            self._generation += 1
            generation = self._generation
            timer = self.timer_factory(
                float(self.delay_seconds),
                lambda: self._fire(generation),
            )
            if hasattr(timer, "daemon"):
                timer.daemon = True
            self._timer = timer
            timer.start()
        return {
            "ok": True,
            "message": self._scheduled_message("zostało zaplanowane"),
        }

    def cancel_shutdown(self) -> dict[str, Any]:
        with self._lock:
            timer = self._timer
            self._timer = None
            self._generation += 1
        if timer is None:
            return {
                "ok": True,
                "message": "Nie ma aktywnego odliczania do wyłączenia komputera.",
            }
        timer.cancel()
        return {
            "ok": True,
            "message": "Anulowałem odliczanie. Komputer pozostanie włączony.",
        }

    def close(self) -> None:
        """Closing JARVIS cancels an unfinished countdown instead of surprising the user."""
        with self._lock:
            timer = self._timer
            self._timer = None
            self._generation += 1
        if timer is not None:
            timer.cancel()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "scheduled": self._timer is not None,
                "delay_seconds": self.delay_seconds,
                "last_execution": self._last_execution,
            }

    def _fire(self, generation: int) -> None:
        with self._lock:
            if self._timer is None or generation != self._generation:
                return
            self._timer = None
        self._invoke_shutdown()

    def _invoke_shutdown(self) -> None:
        # /t 0 deliberately avoids the documented implicit /f used for delays.
        command = [
            str(self.executable),
            "/s",
            "/t",
            "0",
            "/d",
            "p:0:0",
            "/c",
            "JARVIS OS: potwierdzone wyłączenie z telefonu.",
        ]
        try:
            result = self.runner(
                command,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            outcome = "STARTED" if int(result.returncode) == 0 else "FAILED"
        except (OSError, subprocess.SubprocessError, ValueError):
            outcome = "FAILED"
        with self._lock:
            self._last_execution = outcome

    def _scheduled_message(self, verb: str) -> str:
        return (
            f"Wyłączenie komputera {verb} za {self.delay_seconds} sekund. "
            "Możesz je anulować z telefonu przed końcem odliczania."
        )

    def _processed_ids(self) -> list[str]:
        value = self.processed.load()
        values = value.get("request_ids", []) if isinstance(value, dict) else []
        return [
            str(item).lower()
            for item in values
            if self._valid_request_id(item)
        ][-128:]

    def _remember(self, request_id: str) -> bool:
        values = self._processed_ids()
        try:
            self.processed.save({
                "schema_version": 1,
                "request_ids": (values + [request_id.lower()])[-128:],
            })
        except (OSError, RuntimeError, ValueError):
            return False
        return True

    @staticmethod
    def _valid_request_id(value: object) -> bool:
        text = str(value or "").lower()
        return len(text) == 32 and all(char in "0123456789abcdef" for char in text)

    @staticmethod
    def _system_executable() -> Path:
        root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        return root / "System32" / "shutdown.exe"


__all__ = ["WindowsPowerController"]

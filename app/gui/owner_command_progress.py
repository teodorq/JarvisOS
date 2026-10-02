"""Quiet activity heartbeat for long-running owner commands."""

from __future__ import annotations

import time
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer


class OwnerCommandProgress(QObject):
    """Keep the owner status bar alive without adding chat messages."""

    def __init__(
        self,
        window: Any,
        *,
        interval_ms: int = 5_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.clock = clock
        self.interval_ms = max(1_000, min(30_000, int(interval_ms)))
        self.phase = ""
        self.started_at = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self._tick)

    @property
    def active(self) -> bool:
        return bool(self.phase)

    def start(self, phase: str) -> None:
        if phase not in {"planning", "executing"}:
            raise ValueError("unsupported owner command progress phase")
        self.phase = phase
        self.started_at = self.clock()
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()
        self.phase = ""
        self.started_at = 0.0

    def _tick(self) -> None:
        if not self.active:
            return
        elapsed = max(0, int(self.clock() - self.started_at))
        label = (
            "ANALIZUJĘ POLECENIE"
            if self.phase == "planning"
            else "WYKONUJĘ I SPRAWDZAM"
        )
        self.window.console_page.set_state(
            f"{label} • {elapsed} S",
            "accent",
        )


__all__ = ["OwnerCommandProgress"]

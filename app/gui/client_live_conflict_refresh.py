from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from app.gui.client_background_reads import submit_client_read
from app.gui.client_profile_read import read_client_profile


class ClientLiveConflictRefreshRuntime:
    """Read-only periodic refresh for new or changed calendar conflicts."""

    INTERVAL_MS = 60 * 1000

    def __init__(self, window: Any) -> None:
        self.window = window
        self.running = False
        self.timer = QTimer(window)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self.run)

    def arm(self) -> None:
        if not self.timer.isActive():
            self.timer.start()

    def run(self) -> None:
        if self.running:
            return
        if self._busy():
            runtime = self._safe_runtime()
            if runtime is not None:
                runtime.request(
                    self.run,
                    priority=30,
                    kind="live_conflict_refresh",
                )
            return
        profile = read_client_profile(self.window.controller)
        assistant = getattr(self.window.owner_window, "assistant", None)
        natural = getattr(assistant, "natural_actions", None)
        if not profile.get("setup_completed") or natural is None:
            return
        self.running = True
        accepted = submit_client_read(
            self.window, natural.startup_conflict_scan,
            self._scan_finished, self._scan_failed,
        )
        if not accepted:
            self.running = False

    def _scan_finished(self, raw_result: object) -> None:
        self.running = False
        result = dict(raw_result or {})
        if not result.get("should_show"):
            return
        event = {
            "state": "important", "message": str(result.get("message", "")),
            "progress": 0, "requires_confirmation": False,
        }
        runtime = self._safe_runtime()
        if runtime is None:
            self.window._on_client_event(event)
        else:
            runtime.deliver(event, priority=30, kind="calendar_conflict")

    def _scan_failed(self, _error: object) -> None:
        self.running = False

    def _safe_runtime(self):
        getter = getattr(self.window, "_safe_proactivity_runtime", None)
        return getter() if callable(getter) else None

    def _busy(self) -> bool:
        return (
            bool(getattr(self.window.presenter, "busy", False))
            or getattr(self.window.owner_window, "pending_thought", None)
            is not None
        )

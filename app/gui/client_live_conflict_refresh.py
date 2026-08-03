from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer


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
        self.running = True
        try:
            profile = dict(
                self.window.controller.status().get("profile", {}) or {}
            )
            if not profile.get("setup_completed"):
                return
            assistant = getattr(self.window.owner_window, "assistant", None)
            natural = getattr(assistant, "natural_actions", None)
            if natural is None:
                return
            result = dict(natural.startup_conflict_scan() or {})
            if not result.get("should_show"):
                return
            event = {
                "state": "important",
                "message": str(result.get("message", "")),
                "progress": 0,
                "requires_confirmation": False,
            }
            runtime = self._safe_runtime()
            if runtime is None:
                self.window._on_client_event(event)
            else:
                runtime.deliver(
                    event,
                    priority=30,
                    kind="calendar_conflict",
                )
        except Exception:
            return
        finally:
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

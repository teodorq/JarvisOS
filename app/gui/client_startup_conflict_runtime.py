from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer


class ClientStartupConflictRuntime:
    """Reliable, read-only startup scan with bounded delayed retries."""

    DELAYS_MS = (1200, 1800, 2800, 4200, 6000)

    def __init__(self, window: Any) -> None:
        self.window = window
        self.attempt = 0
        self.done = False
        self.timer = QTimer(window)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.run)

    def arm(self) -> None:
        if self.done or self.timer.isActive():
            return
        self.timer.start(self.DELAYS_MS[min(self.attempt, len(self.DELAYS_MS) - 1)])

    def run(self) -> None:
        if self.done:
            return
        if self._busy():
            runtime = self._safe_runtime()
            if runtime is not None:
                runtime.request(
                    self.run, priority=30, kind="startup_conflict_scan"
                )
            else:
                self._retry()
            return
        self.attempt += 1
        try:
            profile = dict(self.window.controller.status().get("profile", {}) or {})
            assistant = getattr(self.window.owner_window, "assistant", None)
            natural = getattr(assistant, "natural_actions", None)
            if natural is None:
                self._retry()
                return
            result = dict(natural.startup_conflict_scan() or {})
        except Exception:
            self._retry()
            return
        if not profile.get("setup_completed"):
            self._finish()
            return
        if not result.get("should_show"):
            reason = str(result.get("notification_reason", ""))
            if (
                result.get("duplicate_suppressed")
                or reason in {"unchanged", "suppressed_by_decision"}
            ):
                self._finish()
                return
            self._retry()
            return
        self._finish()
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
                event, priority=30, kind="calendar_conflict"
            )

    def _safe_runtime(self):
        getter = getattr(self.window, "_safe_proactivity_runtime", None)
        return getter() if callable(getter) else None
    def _busy(self) -> bool:
        return (
            bool(getattr(self.window.presenter, "busy", False))
            or getattr(self.window.owner_window, "pending_thought", None) is not None
        )

    def _retry(self) -> None:
        if self.attempt >= len(self.DELAYS_MS):
            self._finish()
            QTimer.singleShot(150, self.window._show_proactive_brief)
            return
        self.timer.start(self.DELAYS_MS[self.attempt])

    def _finish(self) -> None:
        self.done = True
        self.timer.stop()
        self.window._startup_conflict_scan_done = True

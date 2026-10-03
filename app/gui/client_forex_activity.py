"""Safe client-window delivery of local Forex PAPER activity."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from app.gui.client_background_reads import submit_client_read


class ClientForexActivityRuntime:
    """Poll the local feed and route new events through UI idle policy."""

    def __init__(self, window: Any) -> None:
        self.window = window
        self.timer = QTimer(window)
        profile = getattr(window.owner_window, "performance_profile", None)
        interval = getattr(profile, "client_forex_interval_ms", 30 * 1000)
        if not isinstance(interval, int):
            interval = 30 * 1000
        self.timer.setInterval(max(1000, interval))
        self.timer.timeout.connect(self.poll)

    def arm(self) -> None:
        if self.timer.isActive():
            return
        self.timer.start()
        QTimer.singleShot(1200, self.poll)

    def poll(self) -> None:
        visible = getattr(self.window, "isVisible", None)
        if callable(visible) and not visible():
            return
        assistant = getattr(self.window.owner_window, "assistant", None)
        trading = getattr(assistant, "trading", None)
        feed = getattr(trading, "forex_activity", None)
        poll = getattr(feed, "poll", None)
        if not callable(poll):
            return
        submit_client_read(self.window, poll, self._deliver, lambda _error: None)

    def _deliver(self, event: object) -> None:
        if isinstance(event, dict):
            self.window._safe_proactivity_runtime().deliver(
                event, priority=30, kind="forex_paper"
            )


def arm_client_forex_activity(window: Any) -> None:
    runtime = getattr(window, "_forex_activity_runtime_service", None)
    if runtime is None:
        runtime = ClientForexActivityRuntime(window)
        window._forex_activity_runtime_service = runtime
    runtime.arm()


__all__ = ["ClientForexActivityRuntime", "arm_client_forex_activity"]

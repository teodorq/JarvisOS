from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QTimer

from app.core.performance_profile import load_performance_profile
from app.gui.runtime_preferences import apply_runtime_preferences


class PerformancePowerWatcher(QObject):
    """Refresh the automatic profile only when the power state can matter."""

    INTERVAL_MS = 30_000

    def __init__(self, owner_window: QObject) -> None:
        super().__init__(owner_window)
        self.owner_window = owner_window
        self.timer = QTimer(self)
        self.timer.setInterval(self.INTERVAL_MS)
        self.timer.timeout.connect(self.check)

    def sync(self) -> None:
        if self._selected_profile() == "auto":
            if not self.timer.isActive():
                self.timer.start()
            return
        self.timer.stop()

    def check(self) -> None:
        if self._selected_profile() != "auto":
            self.timer.stop()
            return
        next_profile = load_performance_profile(
            getattr(self.owner_window, "project_root", None)
        )
        current = getattr(self.owner_window, "performance_profile", None)
        if getattr(current, "name", "") != next_profile.name:
            apply_runtime_preferences(self.owner_window)

    def _selected_profile(self) -> str:
        config = getattr(self.owner_window, "business_config", {})
        performance = dict(config.get("performance", {}) or {})
        return str(performance.get("profile", "auto")).strip().casefold()


def connect_performance_power_watcher(owner_window: Any) -> None:
    if not isinstance(owner_window, QObject):
        return
    watcher = getattr(owner_window, "_performance_power_watcher", None)
    if watcher is None:
        watcher = PerformancePowerWatcher(owner_window)
        owner_window._performance_power_watcher = watcher
    watcher.sync()


__all__ = ["PerformancePowerWatcher", "connect_performance_power_watcher"]

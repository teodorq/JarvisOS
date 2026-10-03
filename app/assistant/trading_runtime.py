"""Lazy access to the large trading control graph."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

from app.core.project_paths import resolve_project_root


class LazyTradingRuntime:
    """Keep PAPER notifications light and load the full center on demand."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self._lock = RLock()
        self._activity: Any | None = None
        self._center: Any | None = None

    @property
    def forex_activity(self) -> Any:
        with self._lock:
            if self._activity is not None:
                return self._activity
            if self._center is not None:
                self._activity = self._center.forex_activity
                return self._activity
            from app.market_data.forex_environment import load_forex_environment
            from app.trading.forex_activity import ForexPaperActivityFeed

            load_forex_environment(self.project_root)
            self._activity = ForexPaperActivityFeed(self.project_root)
            return self._activity

    @property
    def loaded(self) -> bool:
        return self._center is not None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._load_center(), name)

    def _load_center(self) -> Any:
        with self._lock:
            if self._center is not None:
                return self._center
            from app.trading.control_center import TradingControlCenter

            center = TradingControlCenter(self.project_root)
            if self._activity is not None:
                center.forex_activity = self._activity
            else:
                self._activity = center.forex_activity
            self._center = center
            return center


__all__ = ["LazyTradingRuntime"]

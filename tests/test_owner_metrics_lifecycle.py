from __future__ import annotations

from unittest.mock import Mock

from app.gui.main_window_runtime import (
    OWNER_METRICS_INTERVAL_MS,
    OWNER_FOREX_INTERVAL_MS,
    set_owner_metrics_active,
)


class _Timer:
    def __init__(self, active: bool = True) -> None:
        self.active = active
        self.interval = 0
        self.stops = 0

    def isActive(self) -> bool:  # noqa: N802 - Qt API
        return self.active

    def start(self, interval: int) -> None:
        self.active = True
        self.interval = interval

    def stop(self) -> None:
        self.active = False
        self.stops += 1


def test_hidden_owner_panel_stops_owner_only_timers() -> None:
    timer = _Timer()
    forex_timer = _Timer()
    window = Mock()
    window.timer = timer
    window._forex_activity_timer = forex_timer

    set_owner_metrics_active(window, False)

    assert not timer.active
    assert timer.stops == 1
    assert not forex_timer.active
    assert forex_timer.stops == 1
    window.update_system_status.assert_not_called()


def test_owner_metrics_resume_and_refresh_immediately() -> None:
    timer = _Timer(active=False)
    forex_timer = _Timer(active=False)
    window = Mock()
    window.timer = timer
    window._forex_activity_timer = forex_timer

    set_owner_metrics_active(window, True)

    assert timer.active
    assert timer.interval == OWNER_METRICS_INTERVAL_MS
    assert forex_timer.active
    assert forex_timer.interval == OWNER_FOREX_INTERVAL_MS
    window.update_system_status.assert_called_once_with()


def test_low_resource_profile_slows_owner_refreshes() -> None:
    timer = _Timer(active=False)
    forex_timer = _Timer(active=False)
    profile = Mock(
        owner_metrics_interval_ms=2000,
        owner_forex_interval_ms=15_000,
    )
    window = Mock(performance_profile=profile)
    window.timer = timer
    window._forex_activity_timer = forex_timer

    set_owner_metrics_active(window, True)

    assert timer.interval == 2000
    assert forex_timer.interval == 15_000


def test_client_only_start_has_no_owner_timer_to_toggle() -> None:
    window = Mock(spec=[])

    set_owner_metrics_active(window, False)

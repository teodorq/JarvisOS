from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from app.gui.client_observer_lifecycle import (
    resume_client_observers,
    suspend_client_observers,
)


class _Timer:
    def __init__(self, active: bool = True) -> None:
        self.active = active
        self.starts = 0
        self.stops = 0

    def isActive(self) -> bool:  # noqa: N802 - Qt API
        return self.active

    def start(self) -> None:
        self.active = True
        self.starts += 1

    def stop(self) -> None:
        self.active = False
        self.stops += 1


def _window(active: bool = True):
    proactive = _Timer(active)
    runtimes = [SimpleNamespace(timer=_Timer(active), arm=Mock()) for _ in range(3)]
    return SimpleNamespace(
        _proactive_timer=proactive,
        _forex_activity_runtime_service=runtimes[0],
        _live_conflict_refresh_service=runtimes[1],
        _startup_conflict_runtime_service=runtimes[2],
    ), proactive, runtimes


def test_owner_mode_suspends_all_client_only_observers() -> None:
    window, proactive, runtimes = _window()

    suspend_client_observers(window)

    assert not proactive.active
    assert proactive.stops == 1
    assert all(not runtime.timer.active for runtime in runtimes)
    assert all(runtime.timer.stops == 1 for runtime in runtimes)


def test_client_mode_resumes_existing_observers() -> None:
    window, proactive, runtimes = _window(active=False)

    resume_client_observers(window)

    assert proactive.active
    assert proactive.starts == 1
    for runtime in runtimes:
        runtime.arm.assert_called_once_with()


def test_lifecycle_is_safe_before_observers_exist() -> None:
    window = SimpleNamespace()

    suspend_client_observers(window)
    resume_client_observers(window)


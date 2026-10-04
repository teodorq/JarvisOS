from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from app.business.business_config import BusinessConfigStore
from app.gui.runtime_preferences import apply_runtime_preferences


class _Timer:
    def __init__(self) -> None:
        self.interval = 0

    def setInterval(self, value: int) -> None:  # noqa: N802 - Qt API
        self.interval = int(value)


def test_low_resource_preferences_apply_to_live_runtimes(tmp_path) -> None:
    store = BusinessConfigStore(tmp_path)
    config = store.update({
        "performance": {"profile": "low_resource"},
        "sound": {"effects_enabled": False},
    })
    halo = SimpleNamespace(set_performance_profile=Mock())
    sound = SimpleNamespace(apply_preferences=Mock())
    client = SimpleNamespace(
        halo=halo,
        presenter=SimpleNamespace(sound_theme=sound),
        _forex_activity_runtime_service=SimpleNamespace(timer=_Timer()),
        _live_conflict_refresh_service=SimpleNamespace(timer=_Timer()),
    )
    owner = SimpleNamespace(
        project_root=tmp_path,
        business_config=config,
        client_window=client,
        timer=_Timer(),
        _forex_activity_timer=_Timer(),
    )

    profile = apply_runtime_preferences(owner)

    assert profile is not None and profile.name == "low_resource"
    assert owner.performance_profile is profile
    assert owner.timer.interval == 2000
    assert owner._forex_activity_timer.interval == 15_000
    assert client._forex_activity_runtime_service.timer.interval == 60_000
    assert client._live_conflict_refresh_service.timer.interval == 120_000
    halo.set_performance_profile.assert_called_once_with(profile)
    sound.apply_preferences.assert_called_once_with(
        enabled=False, performance_profile=profile
    )

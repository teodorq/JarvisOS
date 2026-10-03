from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path

from app.business.business_config import BusinessConfigStore
from app.core.performance_profile import load_performance_profile
from app.core.runtime_maintenance import cleanup_runtime_storage
from app.gui.startup_mode import should_start_client


class _Controller:
    def __init__(self, *, setup: bool = True, remembered: bool = False) -> None:
        self.setup = setup
        self.remembered = remembered

    def profile(self) -> dict[str, bool]:
        return {"setup_completed": self.setup}

    def should_start_client(self) -> bool:
        return self.remembered


def test_preferences_are_persisted_and_invalid_values_are_hardened(tmp_path) -> None:
    store = BusinessConfigStore(tmp_path)
    saved = store.update({
        "ui": {"startup_mode": "client", "start_page": "forex"},
        "performance": {"profile": "low_resource"},
        "sound": {"effects_enabled": False},
    })
    assert saved["ui"]["startup_mode"] == "client"
    assert saved["ui"]["start_page"] == "forex"
    assert saved["performance"]["profile"] == "low_resource"
    assert saved["sound"]["effects_enabled"] is False

    hardened = store.update({
        "ui": {"startup_mode": "unsafe", "start_page": "hidden"},
        "performance": {"profile": "unbounded"},
    })
    assert hardened["ui"]["startup_mode"] == "remember"
    assert hardened["ui"]["start_page"] == "console"
    assert hardened["performance"]["profile"] == "auto"


def test_business_preference_selects_real_performance_profile(tmp_path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "performance.json").write_text(
        json.dumps({"profile": "auto"}), encoding="utf-8"
    )
    BusinessConfigStore(tmp_path).update({
        "performance": {"profile": "low_resource"}
    })

    profile = load_performance_profile(
        tmp_path,
        environment={},
        system_probe=lambda: (32 * 1024**3, 16),
    )

    assert profile.name == "low_resource"


def test_startup_screen_respects_owner_client_and_remember_modes() -> None:
    controller = _Controller(setup=True, remembered=False)
    assert should_start_client(
        controller, {"ui": {"startup_mode": "client"}}
    ) is True
    assert should_start_client(
        controller, {"ui": {"startup_mode": "owner"}}
    ) is False
    assert should_start_client(
        controller, {"ui": {"startup_mode": "remember"}}
    ) is False
    assert should_start_client(
        _Controller(setup=False), {"ui": {"startup_mode": "client"}}
    ) is False


def test_cleanup_compacts_allowlisted_history_and_old_screenshots(tmp_path) -> None:
    autodev = tmp_path / "data" / "autodev"
    screenshots = tmp_path / "data" / "screenshots"
    autodev.mkdir(parents=True)
    screenshots.mkdir(parents=True)
    target = autodev / "full_autonomy_runs.json"
    target.write_text(
        json.dumps({"runs": {"one": {"status": "DONE"}}}, indent=4),
        encoding="utf-8",
    )
    before = target.stat().st_size
    now = datetime.now()
    for index in range(14):
        screenshot = screenshots / f"screen_{index}.png"
        screenshot.write_bytes(b"image")
        stamp = (now - timedelta(minutes=index)).timestamp()
        os.utime(screenshot, (stamp, stamp))

    result = cleanup_runtime_storage(tmp_path)

    assert target.stat().st_size < before
    assert result["saved_bytes"] > 0
    assert result["compacted_files"] == 1
    assert result["removed_screenshots"] == 2
    assert len(list(screenshots.glob("*.png"))) == 12

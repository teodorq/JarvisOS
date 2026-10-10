from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.business.business_config import BusinessConfigStore
from app.core.performance_profile import load_performance_profile
from app.core.runtime_maintenance import (
    cleanup_runtime_storage,
    runtime_storage_status,
)
from app.gui.startup_mode import should_start_client
from app.gui.main_window import MainWindow
from app.assistant.conversation_preferences import load_conversation_preferences


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
        "ui": {
            "startup_mode": "client",
            "start_page": "forex",
            "start_minimized": True,
        },
        "performance": {"profile": "low_resource"},
        "sound": {"effects_enabled": False},
        "notifications": {"desktop_enabled": False},
    })
    assert saved["ui"]["startup_mode"] == "client"
    assert saved["ui"]["start_page"] == "forex"
    assert saved["ui"]["start_minimized"] is True
    assert saved["performance"]["profile"] == "low_resource"
    assert saved["sound"]["effects_enabled"] is False
    assert saved["notifications"]["desktop_enabled"] is False

    hardened = store.update({
        "ui": {
            "startup_mode": "unsafe",
            "start_page": "hidden",
            "start_minimized": "yes",
        },
        "performance": {"profile": "unbounded"},
        "notifications": {"desktop_enabled": "no"},
    })
    assert hardened["ui"]["startup_mode"] == "remember"
    assert hardened["ui"]["start_page"] == "console"
    assert hardened["ui"]["start_minimized"] is False
    assert hardened["performance"]["profile"] == "auto"
    assert hardened["notifications"]["desktop_enabled"] is True


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
    cache = tmp_path / "app" / "feature" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "feature.cpython-313.pyc").write_bytes(b"cache" * 100)
    protected = tmp_path / "data" / "memory" / "important.pyc"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"keep")
    audio = tmp_path / "runtime" / "voice_output" / "cache"
    audio.mkdir(parents=True)
    for index in range(66):
        sample = audio / f"voice_{index:02d}.wav"
        sample.write_bytes(b"voice")
        stamp = (now - timedelta(minutes=index)).timestamp()
        os.utime(sample, (stamp, stamp))

    result = cleanup_runtime_storage(tmp_path)

    assert target.stat().st_size < before
    assert result["saved_bytes"] > 0
    assert result["compacted_files"] == 1
    assert result["removed_screenshots"] == 2
    assert result["removed_audio_files"] == 2
    assert result["removed_cache_files"] == 1
    assert not cache.exists()
    assert protected.read_bytes() == b"keep"
    assert len(list(screenshots.glob("*.png"))) == 12
    assert len(list(audio.glob("*.wav"))) == 64


def test_runtime_status_reports_full_storage_breakdown(tmp_path) -> None:
    sizes = {
        ".venv": 11,
        "data": 13,
        "runtime": 17,
        "archive": 19,
        "assets": 23,
        "AI_PLIKI": 29,
    }
    for name, size in sizes.items():
        directory = tmp_path / name
        directory.mkdir(parents=True)
        (directory / "sample.bin").write_bytes(b"x" * size)

    voice = tmp_path / "runtime" / "voice_output" / "cloud_cache"
    voice.mkdir(parents=True)
    (voice / "reply.wav").write_bytes(b"voice")
    status = runtime_storage_status(tmp_path)

    assert status["environment_bytes"] == sizes[".venv"]
    assert status["archive_bytes"] == sizes["archive"]
    assert status["support_bytes"] == sizes["assets"] + sizes["AI_PLIKI"]
    assert status["audio_cache_files"] == 1
    assert status["audio_cache_bytes"] == len(b"voice")
    assert status["application_bytes"] == sum(sizes.values()) + len(b"voice")
    assert status["largest_category"] == "support"
    assert status["largest_category_bytes"] == sizes["assets"] + sizes["AI_PLIKI"]
    assert status["cleanup_candidate_bytes"] == 0


def test_cleanup_covers_all_project_code_without_touching_environment(tmp_path) -> None:
    project_caches = (
        tmp_path / "__pycache__",
        tmp_path / "software_engineer" / "feature" / "__pycache__",
    )
    for cache in project_caches:
        cache.mkdir(parents=True)
        (cache / "module.cpython-313.pyc").write_bytes(b"regenerable")
    environment_cache = tmp_path / ".venv" / "Lib" / "site-packages" / "__pycache__"
    environment_cache.mkdir(parents=True)
    protected = environment_cache / "package.cpython-313.pyc"
    protected.write_bytes(b"installed dependency")

    result = cleanup_runtime_storage(tmp_path)

    assert result["removed_cache_dirs"] == len(project_caches)
    assert result["removed_cache_files"] == len(project_caches)
    assert all(not cache.exists() for cache in project_caches)
    assert protected.read_bytes() == b"installed dependency"


def test_owner_settings_save_conversation_outside_business_config(tmp_path) -> None:
    store = BusinessConfigStore(tmp_path)
    owner = SimpleNamespace(
        project_root=tmp_path,
        config_store=store,
        business_config=store.ensure(),
        _apply_runtime_config=Mock(),
        settings_page=SimpleNamespace(set_feedback=Mock()),
        console_page=SimpleNamespace(append=Mock()),
    )

    MainWindow._save_business_settings(owner, {
        "organization": "Kacper",
        "_conversation": {
            "style": "detailed",
            "question_mode": "engaged",
        },
    })

    assert "_conversation" not in store.ensure()
    assert load_conversation_preferences(tmp_path) == {
        "style": "detailed",
        "question_mode": "engaged",
    }
    owner._apply_runtime_config.assert_called_once_with()

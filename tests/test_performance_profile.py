from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.performance_profile import load_performance_profile


def _root(profile: str) -> TemporaryDirectory:
    temporary = TemporaryDirectory()
    config = Path(temporary.name) / "config"
    config.mkdir()
    (config / "performance.json").write_text(
        json.dumps({"profile": profile}), encoding="utf-8"
    )
    return temporary


def test_auto_selects_low_resource_for_small_machine() -> None:
    with _root("auto") as root:
        profile = load_performance_profile(
            root,
            environment={},
            system_probe=lambda: (4 * 1024**3, 4),
        )
    assert profile.name == "low_resource"
    assert profile.lazy_voice is True


def test_auto_keeps_balanced_profile_for_capable_machine() -> None:
    with _root("auto") as root:
        profile = load_performance_profile(
            root,
            environment={},
            system_probe=lambda: (16 * 1024**3, 8),
        )
    assert profile.name == "balanced"
    assert profile.orb_stride_multiplier == 1


def test_environment_override_wins_over_file_and_probe() -> None:
    with _root("balanced") as root:
        profile = load_performance_profile(
            root,
            environment={"JARVIS_OS_PERFORMANCE_PROFILE": "low_resource"},
            system_probe=lambda: (32 * 1024**3, 16),
        )
    assert profile.name == "low_resource"

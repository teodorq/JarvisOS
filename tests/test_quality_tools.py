from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools.check_runtime_health import collect_runtime_health, directory_size
from tools.run_quality_checks import QUICK_TESTS, build_commands


def test_quick_tier_contains_runtime_and_retention_regressions() -> None:
    commands = build_commands("quick")
    assert "tests/test_runtime_startup_profile.py" in commands[0]
    assert "tests/test_storage_retention.py" in commands[0]
    assert "tests/test_autodev_storage_retention.py" in commands[0]
    assert tuple(commands[0][-len(QUICK_TESTS):]) == QUICK_TESTS


def test_full_tier_runs_complete_suite_then_compile_check() -> None:
    commands = build_commands("full")
    assert commands[0][-1] == "tests"
    assert "compileall" in commands[1]


def test_directory_size_is_bounded_to_selected_directory() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "nested").mkdir()
        (root / "one.bin").write_bytes(b"123")
        (root / "nested" / "two.bin").write_bytes(b"4567")
        assert directory_size(root) == 7


def test_runtime_health_tracks_real_window_construction() -> None:
    with TemporaryDirectory() as temporary, patch(
        "tools.check_runtime_health.measure_main_window_import",
        return_value=0.7,
    ), patch(
        "tools.check_runtime_health.measure_main_window_construction",
        return_value=0.4,
    ):
        report = collect_runtime_health(temporary)
    assert report["main_window_import_seconds"] == 0.7
    assert report["main_window_construct_seconds"] == 0.4
    assert report["construction_within_target"] is True

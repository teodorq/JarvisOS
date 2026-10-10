from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

from app.core.autodev_compaction import compact_autodev_json
from app.core.performance_profile import load_performance_profile
from app.core.project_paths import resolve_project_root
from app.core.regenerable_cache_cleanup import (
    cleanup_regenerable_caches,
    regenerable_cache_status,
)
from app.core.storage_retention import (
    audio_cache_retention_status,
    enforce_audio_cache_retention,
    enforce_screenshot_retention,
    screenshot_retention_status,
)


_AUDIO_CACHE_DIRECTORIES = (
    Path("runtime/voice_output/cache"),
    Path("runtime/voice_output/cloud_cache"),
)


def directory_size(path: Path) -> int:
    total = 0
    if not path.is_dir():
        return total
    for current, _directories, files in os.walk(path):
        for filename in files:
            try:
                total += (Path(current) / filename).stat().st_size
            except OSError:
                continue
    return total


def runtime_storage_status(project_root: str | Path | None = None) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    screenshots = root / "data" / "screenshots"
    usage = shutil.disk_usage(root)
    caches = regenerable_cache_status(root)
    environment_bytes = directory_size(root / ".venv")
    data_bytes = directory_size(root / "data")
    runtime_bytes = directory_size(root / "runtime")
    archive_bytes = directory_size(root / "archive")
    support_bytes = sum(
        directory_size(root / name) for name in ("assets", "AI_PLIKI")
    )
    audio = _audio_cache_status(root)
    audio_candidates = _audio_cleanup_status(root)
    screenshot_bytes = sum(
        path.stat().st_size for path in screenshots.glob("*") if path.is_file()
    )
    screenshot_candidates = screenshot_retention_status(screenshots)
    storage_groups = {
        "environment": environment_bytes,
        "data": data_bytes,
        "runtime": runtime_bytes,
        "archive": archive_bytes,
        "support": support_bytes,
    }
    largest_category = max(storage_groups, key=storage_groups.get)
    cleanup_candidate_bytes = (
        int(caches.get("cache_bytes", 0))
        + int(screenshot_candidates.get("candidate_bytes", 0))
        + int(audio_candidates.get("audio_candidate_bytes", 0))
    )
    cleanup_candidate_files = (
        int(caches.get("cache_files", 0))
        + int(screenshot_candidates.get("candidate_files", 0))
        + int(audio_candidates.get("audio_candidate_files", 0))
    )
    return {
        "profile": load_performance_profile(root).name,
        "application_bytes": (
            environment_bytes + data_bytes + runtime_bytes
            + archive_bytes + support_bytes
        ),
        "environment_bytes": environment_bytes,
        "data_bytes": data_bytes,
        "runtime_bytes": runtime_bytes,
        "archive_bytes": archive_bytes,
        "support_bytes": support_bytes,
        "autodev_bytes": directory_size(root / "data" / "autodev"),
        "screenshot_count": sum(1 for path in screenshots.glob("*") if path.is_file()),
        "screenshot_bytes": screenshot_bytes,
        "screenshot_candidate_files": int(
            screenshot_candidates.get("candidate_files", 0)
        ),
        "screenshot_candidate_bytes": int(
            screenshot_candidates.get("candidate_bytes", 0)
        ),
        "largest_category": largest_category,
        "largest_category_bytes": storage_groups[largest_category],
        "cleanup_candidate_files": cleanup_candidate_files,
        "cleanup_candidate_bytes": cleanup_candidate_bytes,
        "disk_free_bytes": usage.free,
        **audio,
        **audio_candidates,
        **caches,
    }


def cleanup_runtime_storage(project_root: str | Path | None = None) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    compacted = compact_autodev_json(root, apply=True)
    screenshots = enforce_screenshot_retention(root / "data" / "screenshots")
    audio = _cleanup_audio_caches(root)
    caches = cleanup_regenerable_caches(root)
    return {
        "saved_bytes": int(compacted.get("saved_bytes", 0))
        + int(screenshots.get("removed_bytes", 0))
        + int(audio.get("removed_audio_bytes", 0))
        + int(caches.get("removed_cache_bytes", 0)),
        "compacted_files": sum(
            item.get("status") == "COMPACTED"
            for item in compacted.get("files", [])
        ),
        "removed_screenshots": int(screenshots.get("removed_files", 0)),
        **audio,
        **caches,
        "status": runtime_storage_status(root),
    }


def _audio_cache_status(root: Path) -> dict[str, int]:
    files = 0
    size = 0
    for relative in _AUDIO_CACHE_DIRECTORIES:
        directory = (root / relative).resolve(strict=False)
        try:
            directory.relative_to(root)
        except ValueError:
            continue
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.casefold() != ".wav":
                continue
            try:
                files += 1
                size += path.stat().st_size
            except OSError:
                continue
    return {"audio_cache_files": files, "audio_cache_bytes": size}


def _cleanup_audio_caches(root: Path) -> dict[str, int]:
    removed_files = 0
    removed_bytes = 0
    for relative in _AUDIO_CACHE_DIRECTORIES:
        directory = (root / relative).resolve(strict=False)
        try:
            directory.relative_to(root)
        except ValueError:
            continue
        result = enforce_audio_cache_retention(directory)
        removed_files += int(result.get("removed_files", 0))
        removed_bytes += int(result.get("removed_bytes", 0))
    return {
        "removed_audio_files": removed_files,
        "removed_audio_bytes": removed_bytes,
    }


def _audio_cleanup_status(root: Path) -> dict[str, int]:
    candidate_files = 0
    candidate_bytes = 0
    for relative in _AUDIO_CACHE_DIRECTORIES:
        directory = (root / relative).resolve(strict=False)
        try:
            directory.relative_to(root)
        except ValueError:
            continue
        result = audio_cache_retention_status(directory)
        candidate_files += int(result.get("candidate_files", 0))
        candidate_bytes += int(result.get("candidate_bytes", 0))
    return {
        "audio_candidate_files": candidate_files,
        "audio_candidate_bytes": candidate_bytes,
    }


__all__ = ["cleanup_runtime_storage", "directory_size", "runtime_storage_status"]

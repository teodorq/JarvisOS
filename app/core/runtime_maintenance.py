from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

from app.core.autodev_compaction import compact_autodev_json
from app.core.performance_profile import load_performance_profile
from app.core.project_paths import resolve_project_root
from app.core.storage_retention import enforce_screenshot_retention


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
    return {
        "profile": load_performance_profile(root).name,
        "data_bytes": directory_size(root / "data"),
        "autodev_bytes": directory_size(root / "data" / "autodev"),
        "screenshot_count": sum(1 for path in screenshots.glob("*") if path.is_file()),
        "disk_free_bytes": usage.free,
    }


def cleanup_runtime_storage(project_root: str | Path | None = None) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    compacted = compact_autodev_json(root, apply=True)
    screenshots = enforce_screenshot_retention(root / "data" / "screenshots")
    return {
        "saved_bytes": int(compacted.get("saved_bytes", 0))
        + int(screenshots.get("removed_bytes", 0)),
        "compacted_files": sum(
            item.get("status") == "COMPACTED"
            for item in compacted.get("files", [])
        ),
        "removed_screenshots": int(screenshots.get("removed_files", 0)),
        "status": runtime_storage_status(root),
    }


__all__ = ["cleanup_runtime_storage", "directory_size", "runtime_storage_status"]

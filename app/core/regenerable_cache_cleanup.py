from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

from app.core.project_paths import resolve_project_root


_CACHE_PARENTS = ("app", "tests", "tools", "cloud_service")


def regenerable_cache_status(
    project_root: str | Path | None = None,
) -> dict[str, int]:
    root = resolve_project_root(project_root)
    targets = _cache_targets(root)
    files, size = _target_totals(targets)
    return {"cache_dirs": len(targets), "cache_files": files, "cache_bytes": size}


def cleanup_regenerable_caches(
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    targets = _cache_targets(root)
    files, size = _target_totals(targets)
    removed_dirs = 0
    errors = 0
    for target in sorted(targets, key=lambda value: len(value.parts), reverse=True):
        if not _allowed_target(root, target) or target.is_symlink():
            errors += 1
            continue
        try:
            shutil.rmtree(target)
            removed_dirs += 1
        except OSError:
            errors += 1
    return {
        "removed_cache_dirs": removed_dirs,
        "removed_cache_files": files if not errors else 0,
        "removed_cache_bytes": size if not errors else 0,
        "cache_errors": errors,
    }


def _cache_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    pytest_cache = root / ".pytest_cache"
    if pytest_cache.is_dir() and not pytest_cache.is_symlink():
        targets.append(pytest_cache)
    for name in _CACHE_PARENTS:
        parent = root / name
        if not parent.is_dir() or parent.is_symlink():
            continue
        targets.extend(
            path for path in parent.rglob("__pycache__")
            if path.is_dir() and not path.is_symlink()
        )
    return targets


def _allowed_target(root: Path, target: Path) -> bool:
    resolved_root = root.resolve(strict=False)
    resolved = target.resolve(strict=False)
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError:
        return False
    if relative == Path(".pytest_cache"):
        return True
    return (
        len(relative.parts) >= 2
        and relative.parts[0] in _CACHE_PARENTS
        and relative.name == "__pycache__"
    )


def _target_totals(targets: list[Path]) -> tuple[int, int]:
    files = 0
    size = 0
    for target in targets:
        for current, directories, filenames in os.walk(target):
            directories[:] = [
                name for name in directories
                if not (Path(current) / name).is_symlink()
            ]
            for filename in filenames:
                path = Path(current) / filename
                try:
                    if not path.is_symlink():
                        files += 1
                        size += path.stat().st_size
                except OSError:
                    continue
    return files, size


__all__ = ["cleanup_regenerable_caches", "regenerable_cache_status"]

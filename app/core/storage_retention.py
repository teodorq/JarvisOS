from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScreenshotRetentionPolicy:
    max_files: int = 12
    max_total_bytes: int = 32 * 1024 * 1024
    max_age_days: int = 14

    def __post_init__(self) -> None:
        if self.max_files < 1:
            raise ValueError("max_files must be positive")
        if self.max_total_bytes < 1:
            raise ValueError("max_total_bytes must be positive")
        if self.max_age_days < 1:
            raise ValueError("max_age_days must be positive")


@dataclass(frozen=True, slots=True)
class AudioCacheRetentionPolicy:
    max_files: int = 64
    max_total_bytes: int = 64 * 1024 * 1024
    max_age_days: int = 45

    def __post_init__(self) -> None:
        if self.max_files < 1:
            raise ValueError("max_files must be positive")
        if self.max_total_bytes < 1:
            raise ValueError("max_total_bytes must be positive")
        if self.max_age_days < 1:
            raise ValueError("max_age_days must be positive")


def enforce_screenshot_retention(
    directory: str | Path,
    *,
    policy: ScreenshotRetentionPolicy | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Bound local screenshots by age, count and bytes inside one directory."""
    root = Path(directory).resolve(strict=False)
    selected = policy or ScreenshotRetentionPolicy()
    removable, _removable_bytes, kept_files = _retention_plan(
        root,
        suffixes={".png", ".jpg", ".jpeg", ".webp"},
        max_files=selected.max_files,
        max_total_bytes=selected.max_total_bytes,
        max_age_days=selected.max_age_days,
        now=now,
    )
    removed_files = 0
    removed_bytes = 0
    for path, size in removable:
        try:
            path.resolve(strict=False).relative_to(root)
            path.unlink()
        except (OSError, ValueError):
            continue
        removed_files += 1
        removed_bytes += size
    return {
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
        "kept_files": kept_files,
    }


def screenshot_retention_status(
    directory: str | Path,
    *,
    policy: ScreenshotRetentionPolicy | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Preview safe screenshot cleanup without modifying any file."""
    selected = policy or ScreenshotRetentionPolicy()
    removable, removable_bytes, kept_files = _retention_plan(
        Path(directory).resolve(strict=False),
        suffixes={".png", ".jpg", ".jpeg", ".webp"},
        max_files=selected.max_files,
        max_total_bytes=selected.max_total_bytes,
        max_age_days=selected.max_age_days,
        now=now,
    )
    return {
        "candidate_files": len(removable),
        "candidate_bytes": removable_bytes,
        "kept_files": kept_files,
    }


def enforce_audio_cache_retention(
    directory: str | Path,
    *,
    policy: AudioCacheRetentionPolicy | None = None,
    current_file: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Bound generated WAV files while preserving the file just played."""
    root = Path(directory).resolve(strict=False)
    selected = policy or AudioCacheRetentionPolicy()
    if not root.is_dir():
        return {"removed_files": 0, "removed_bytes": 0, "kept_files": 0}

    protected: Path | None = None
    if current_file is not None:
        candidate = Path(current_file).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError:
            candidate = None
        if candidate is not None and candidate.is_file():
            protected = candidate
            try:
                candidate.touch()
            except OSError:
                pass

    removable, _removable_bytes, kept_files = _retention_plan(
        root,
        suffixes={".wav"},
        max_files=selected.max_files,
        max_total_bytes=selected.max_total_bytes,
        max_age_days=selected.max_age_days,
        protected=protected,
        now=now,
    )
    removed_files = 0
    removed_bytes = 0
    for path, size in removable:
        try:
            path.unlink()
        except OSError:
            continue
        removed_files += 1
        removed_bytes += size
    return {
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
        "kept_files": kept_files,
    }


def audio_cache_retention_status(
    directory: str | Path,
    *,
    policy: AudioCacheRetentionPolicy | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Preview safe generated-audio cleanup without modifying any file."""
    selected = policy or AudioCacheRetentionPolicy()
    removable, removable_bytes, kept_files = _retention_plan(
        Path(directory).resolve(strict=False),
        suffixes={".wav"},
        max_files=selected.max_files,
        max_total_bytes=selected.max_total_bytes,
        max_age_days=selected.max_age_days,
        now=now,
    )
    return {
        "candidate_files": len(removable),
        "candidate_bytes": removable_bytes,
        "kept_files": kept_files,
    }


def _retention_plan(
    root: Path,
    *,
    suffixes: set[str],
    max_files: int,
    max_total_bytes: int,
    max_age_days: int,
    protected: Path | None = None,
    now: datetime | None = None,
) -> tuple[list[tuple[Path, int]], int, int]:
    if not root.is_dir():
        return [], 0, 0
    inventory: list[tuple[Path, Path, int, float]] = []
    for item in root.iterdir():
        if not item.is_file() or item.suffix.casefold() not in suffixes:
            continue
        try:
            resolved = item.resolve(strict=False)
            resolved.relative_to(root)
            stat = item.stat()
        except (OSError, ValueError):
            continue
        inventory.append((item, resolved, stat.st_size, stat.st_mtime))
    inventory.sort(key=lambda entry: entry[3], reverse=True)
    cutoff = ((now or datetime.now()) - timedelta(days=max_age_days)).timestamp()
    total_kept = 0
    kept_files = 0
    removable: list[tuple[Path, int]] = []
    removable_bytes = 0
    for index, (path, resolved, size, modified) in enumerate(inventory):
        keep_protected = protected is not None and resolved == protected
        keep_newest = index == 0
        should_remove = not (keep_protected or keep_newest) and (
            index >= max_files
            or modified < cutoff
            or total_kept + size > max_total_bytes
        )
        if should_remove:
            removable.append((path, size))
            removable_bytes += size
            continue
        kept_files += 1
        total_kept += size
    return removable, removable_bytes, kept_files


__all__ = [
    "AudioCacheRetentionPolicy",
    "ScreenshotRetentionPolicy",
    "audio_cache_retention_status",
    "enforce_audio_cache_retention",
    "enforce_screenshot_retention",
    "screenshot_retention_status",
]

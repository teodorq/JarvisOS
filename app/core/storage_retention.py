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
    if not root.is_dir():
        return {"removed_files": 0, "removed_bytes": 0, "kept_files": 0}
    candidates = sorted(
        (
            item
            for item in root.iterdir()
            if item.is_file() and item.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}
        ),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    cutoff = (now or datetime.now()) - timedelta(days=selected.max_age_days)
    total_kept = 0
    removed_files = 0
    removed_bytes = 0
    kept_files = 0
    for index, path in enumerate(candidates):
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        keep_newest = index == 0
        should_remove = not keep_newest and (
            index >= selected.max_files
            or modified < cutoff
            or total_kept + stat.st_size > selected.max_total_bytes
        )
        if should_remove:
            try:
                path.resolve(strict=False).relative_to(root)
                path.unlink()
            except (OSError, ValueError):
                continue
            removed_files += 1
            removed_bytes += stat.st_size
            continue
        kept_files += 1
        total_kept += stat.st_size
    return {
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
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

    candidates = sorted(
        (
            item
            for item in root.iterdir()
            if item.is_file() and item.suffix.casefold() == ".wav"
        ),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    cutoff = (now or datetime.now()) - timedelta(days=selected.max_age_days)
    total_kept = 0
    removed_files = 0
    removed_bytes = 0
    kept_files = 0
    for index, path in enumerate(candidates):
        try:
            resolved = path.resolve(strict=False)
            resolved.relative_to(root)
            stat = path.stat()
        except (OSError, ValueError):
            continue
        modified = datetime.fromtimestamp(stat.st_mtime)
        keep_current = protected is not None and resolved == protected
        keep_newest = index == 0
        should_remove = not (keep_current or keep_newest) and (
            index >= selected.max_files
            or modified < cutoff
            or total_kept + stat.st_size > selected.max_total_bytes
        )
        if should_remove:
            try:
                path.unlink()
            except OSError:
                continue
            removed_files += 1
            removed_bytes += stat.st_size
            continue
        kept_files += 1
        total_kept += stat.st_size
    return {
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
        "kept_files": kept_files,
    }


__all__ = [
    "AudioCacheRetentionPolicy",
    "ScreenshotRetentionPolicy",
    "enforce_audio_cache_retention",
    "enforce_screenshot_retention",
]

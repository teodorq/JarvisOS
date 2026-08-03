from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any
import uuid

from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clean_text(value: object, *, limit: int = 500) -> str:
    return " ".join(str(value).split()).strip()[:limit]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def sha256_file(path: Path, *, max_bytes: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    remaining = max_bytes
    with path.open("rb") as stream:
        while remaining > 0:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    if path.stat().st_size > max_bytes:
        digest.update(f"|SIZE={path.stat().st_size}".encode("ascii"))
    return digest.hexdigest()


def tokens(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9ąćęłńóśźż]+", str(value).casefold())
        if len(token) > 1
    }


def safe_project_path(
    project_root: str | Path | None,
    value: str | Path | None,
    *,
    default_relative: str,
) -> Path:
    root = resolve_project_root(project_root)
    candidate = Path(value) if value is not None and str(value).strip() else root / default_relative
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.expanduser().resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("Ścieżka musi znajdować się wewnątrz katalogu JARVIS OS.") from error
    return candidate


def summarize_mapping(value: dict[str, Any], keys: tuple[str, ...]) -> str:
    return ", ".join(f"{key}={value.get(key, 0)}" for key in keys)

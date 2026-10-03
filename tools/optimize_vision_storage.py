"""Convert legacy JARVIS screenshots to verified, compact WebP files."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image


LEGACY_SUFFIXES = {".png", ".jpg", ".jpeg"}


def optimize_legacy_screenshots(
    project_root: str | Path,
    *,
    apply: bool = False,
    quality: int = 82,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    screenshot_dir = (root / "data" / "screenshots").resolve()
    if screenshot_dir != root / "data" / "screenshots":
        raise ValueError("Nieprawidłowy katalog zrzutów ekranu.")
    if not screenshot_dir.exists():
        return _result(apply=apply)

    result = _result(apply=apply)
    candidates = sorted(
        path for path in screenshot_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in LEGACY_SUFFIXES
    )
    for source in candidates:
        destination = source.with_suffix(".webp")
        if destination.exists():
            result["skipped"] += 1
            continue
        try:
            encoded, dimensions = _encode(source, quality)
        except (OSError, ValueError):
            result["failed"] += 1
            continue
        source_size = source.stat().st_size
        if len(encoded) >= source_size:
            result["skipped"] += 1
            continue
        result["candidates"] += 1
        result["bytes_before"] += source_size
        result["bytes_after"] += len(encoded)
        if apply:
            _replace_verified(source, destination, encoded, dimensions)
            result["converted"] += 1
    result["bytes_saved"] = result["bytes_before"] - result["bytes_after"]
    return result


def _encode(source: Path, quality: int) -> tuple[bytes, tuple[int, int]]:
    with Image.open(source) as image:
        image.load()
        dimensions = image.size
        converted = image.convert("RGB")
        buffer = BytesIO()
        converted.save(
            buffer, format="WEBP", quality=max(1, min(100, int(quality))), method=1
        )
    encoded = buffer.getvalue()
    with Image.open(BytesIO(encoded)) as check:
        check.verify()
    return encoded, dimensions


def _replace_verified(
    source: Path,
    destination: Path,
    encoded: bytes,
    dimensions: tuple[int, int],
) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_bytes(encoded)
        with Image.open(temporary) as check:
            check.load()
            if check.size != dimensions:
                raise ValueError("Wymiary obrazu zmieniły się podczas konwersji.")
        source_stat = source.stat()
        os.replace(temporary, destination)
        os.utime(destination, (source_stat.st_atime, source_stat.st_mtime))
        source.unlink()
    finally:
        temporary.unlink(missing_ok=True)


def _result(*, apply: bool) -> dict[str, Any]:
    return {
        "mode": "apply" if apply else "dry-run",
        "candidates": 0,
        "converted": 0,
        "skipped": 0,
        "failed": 0,
        "bytes_before": 0,
        "bytes_after": 0,
        "bytes_saved": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--quality", type=int, default=82)
    arguments = parser.parse_args()
    result = optimize_legacy_screenshots(
        arguments.project_root,
        apply=arguments.apply,
        quality=arguments.quality,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

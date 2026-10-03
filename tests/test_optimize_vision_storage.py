from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.optimize_vision_storage import optimize_legacy_screenshots


def _legacy_screenshot(root: Path, name: str = "screen.png") -> Path:
    directory = root / "data" / "screenshots"
    directory.mkdir(parents=True)
    path = directory / name
    Image.new("RGB", (800, 600), (8, 26, 44)).save(path, format="PNG")
    return path


def test_dry_run_reports_savings_without_modifying_image() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = _legacy_screenshot(root)

        result = optimize_legacy_screenshots(root)

        assert result["candidates"] == 1
        assert result["converted"] == 0
        assert result["bytes_saved"] > 0
        assert source.exists()
        assert not source.with_suffix(".webp").exists()


def test_apply_replaces_source_only_after_verified_conversion() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = _legacy_screenshot(root)
        before = source.stat().st_size

        result = optimize_legacy_screenshots(root, apply=True)
        destination = source.with_suffix(".webp")

        assert result["converted"] == 1
        assert not source.exists()
        assert destination.exists()
        assert destination.stat().st_size < before
        with Image.open(destination) as image:
            assert image.size == (800, 600)


def test_existing_webp_is_never_overwritten() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = _legacy_screenshot(root)
        destination = source.with_suffix(".webp")
        destination.write_bytes(b"existing")

        result = optimize_legacy_screenshots(root, apply=True)

        assert result["skipped"] == 1
        assert source.exists()
        assert destination.read_bytes() == b"existing"

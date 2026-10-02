from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sysconfig
from typing import Iterable


GOOGLE_DISCOVERY_KEEP = frozenset({
    "calendar.v3.json",
    "discovery.v1.json",
    "drive.v3.json",
    "gmail.v1.json",
})
SPEECH_UNUSED_ITEMS = (
    "pocketsphinx-data",
    "flac-linux-x86",
    "flac-linux-x86_64",
    "flac-mac",
)


def optimize_runtime_dependencies(
    site_packages: str | Path,
    *,
    apply: bool = False,
) -> dict[str, int | bool]:
    """Remove bundled assets JARVIS never calls, inside one site-packages root."""
    root = Path(site_packages).resolve(strict=True)
    if not root.is_dir() or root.name.casefold() != "site-packages":
        raise ValueError("Expected an existing site-packages directory.")
    candidates = list(_google_candidates(root)) + list(_speech_candidates(root))
    removed_files = 0
    removed_directories = 0
    reclaimed_bytes = sum(_path_size(path) for path in candidates)
    if apply:
        for path in candidates:
            _assert_inside(path, root)
            if path.is_dir():
                shutil.rmtree(path)
                removed_directories += 1
            elif path.is_file():
                path.unlink()
                removed_files += 1
    return {
        "applied": apply,
        "candidate_count": len(candidates),
        "removed_files": removed_files,
        "removed_directories": removed_directories,
        "reclaimed_bytes": reclaimed_bytes,
    }


def _google_candidates(root: Path) -> Iterable[Path]:
    documents = root / "googleapiclient" / "discovery_cache" / "documents"
    if not documents.is_dir():
        return ()
    return tuple(
        path
        for path in documents.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and path.suffix.casefold() == ".json"
        and path.name not in GOOGLE_DISCOVERY_KEEP
    )


def _speech_candidates(root: Path) -> Iterable[Path]:
    package = root / "speech_recognition"
    if not package.is_dir():
        return ()
    return tuple(
        path
        for name in SPEECH_UNUSED_ITEMS
        if (path := package / name).exists() and not path.is_symlink()
    )


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _assert_inside(path: Path, root: Path) -> None:
    path.resolve(strict=False).relative_to(root)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trim unused bundled API and speech assets from JARVIS OS."
    )
    parser.add_argument(
        "--site-packages",
        default=sysconfig.get_paths()["purelib"],
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = optimize_runtime_dependencies(
        args.site_packages,
        apply=args.apply,
    )
    action = "Odzyskano" if args.apply else "Można odzyskać"
    mebibytes = int(result["reclaimed_bytes"]) / 1024**2
    print(f"{action} {mebibytes:.1f} MiB; elementy: {result['candidate_count']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

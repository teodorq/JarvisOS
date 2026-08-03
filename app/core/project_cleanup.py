from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from app.core.project_paths import (
    resolve_project_root,
)


def clean_python_caches(
    project_root: str | Path | None = None,
) -> dict[str, int]:
    root = resolve_project_root(
        project_root
    )
    removed_directories = 0
    removed_files = 0

    for directory in sorted(
        root.rglob("__pycache__"),
        key=lambda item: len(
            item.parts
        ),
        reverse=True,
    ):
        if not directory.is_dir():
            continue

        try:
            directory.resolve(
                strict=False
            ).relative_to(
                root
            )
        except ValueError:
            continue

        shutil.rmtree(
            directory,
            ignore_errors=True,
        )

        if not directory.exists():
            removed_directories += 1

    for pattern in (
        "*.pyc",
        "*.pyo",
    ):
        for file_path in root.rglob(
            pattern
        ):
            try:
                file_path.resolve(
                    strict=False
                ).relative_to(
                    root
                )
            except ValueError:
                continue

            try:
                file_path.unlink()
                removed_files += 1
            except OSError:
                raise RuntimeError("AutoDev: przechwycony wyjątek")

    return {
        "removed_directories": (
            removed_directories
        ),
        "removed_files": removed_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Usuwa wyłącznie cache Pythona "
            "wewnątrz projektu JARVIS OS."
        )
    )
    parser.add_argument(
        "--project-root",
        default=None,
    )
    args = parser.parse_args()
    result = clean_python_caches(
        args.project_root
    )
    print(
        "Usunięte katalogi __pycache__: "
        f"{result['removed_directories']}"
    )
    print(
        "Usunięte pliki .pyc/.pyo: "
        f"{result['removed_files']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

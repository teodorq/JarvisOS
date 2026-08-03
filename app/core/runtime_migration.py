from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from .project_paths import ProjectPaths


class RuntimeDataMigrator:
    """Migrates legacy runtime files and repairs regenerable cache."""

    def __init__(
        self,
        project_root: str | Path | None = None,
    ) -> None:
        self.paths = ProjectPaths.from_value(
            project_root
        )
        self.archive_dir = (
            self.paths.archive
            / "runtime_migration"
        )

    def run(
        self,
        *,
        repair_cache: bool = False,
        max_cache_bytes: int = 10 * 1024 * 1024,
    ) -> dict[str, Any]:
        self.paths.ensure_runtime_directories()

        migration = self.migrate_legacy_files()
        cache = self.inspect_symbol_cache()

        if repair_cache:
            cache = self.repair_symbol_cache(
                max_bytes=max_cache_bytes
            )

        return {
            "success": True,
            "project_root": str(
                self.paths.root
            ),
            "migration": migration,
            "symbol_cache": cache,
        }

    def migrate_legacy_files(
        self,
    ) -> list[dict[str, Any]]:
        mappings = (
            (
                self.paths.root / "memory.json",
                self.paths.main_memory_file,
            ),
            (
                self.paths.root / "goals.json",
                self.paths.goal_memory_file,
            ),
            (
                self.paths.root / "reflections.json",
                self.paths.reflection_memory_file,
            ),
            (
                self.paths.root / "symbol_index.json",
                self.paths.symbol_index_cache,
            ),
            (
                self.paths.root
                / "cache/symbol_index.json",
                self.paths.symbol_index_cache,
            ),
            (
                self.paths.data
                / "symbol_index.json",
                self.paths.symbol_index_cache,
            ),
        )

        results: list[dict[str, Any]] = []

        for source, destination in mappings:
            if (
                source.resolve(
                    strict=False
                )
                == destination.resolve(
                    strict=False
                )
            ):
                continue

            if not source.is_file():
                continue

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if destination.exists():
                archived = self._archive(
                    source,
                    reason="duplicate",
                )
                status = "ARCHIVED_DUPLICATE"
            else:
                shutil.move(
                    str(source),
                    str(destination),
                )
                archived = None
                status = "MIGRATED"

            results.append(
                {
                    "source": str(source),
                    "destination": str(
                        destination
                    ),
                    "status": status,
                    "archive": (
                        str(archived)
                        if archived is not None
                        else ""
                    ),
                }
            )

        return results

    def inspect_symbol_cache(
        self,
    ) -> dict[str, Any]:
        path = self.paths.symbol_index_cache

        if not path.is_file():
            return {
                "status": "MISSING",
                "path": str(path),
                "size_bytes": 0,
                "valid_json": False,
            }

        valid_json = self._is_valid_json(
            path
        )

        return {
            "status": (
                "READY"
                if valid_json
                else "INVALID_JSON"
            ),
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "valid_json": valid_json,
        }

    def repair_symbol_cache(
        self,
        *,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> dict[str, Any]:
        if max_bytes < 1:
            raise ValueError(
                "max_bytes musi być większe od zera."
            )

        path = self.paths.symbol_index_cache
        inspection = self.inspect_symbol_cache()

        if inspection["status"] == "MISSING":
            return inspection

        reason = ""

        if not inspection["valid_json"]:
            reason = "invalid"
        elif inspection["size_bytes"] > max_bytes:
            reason = "oversized"

        if not reason:
            return inspection

        archived = self._archive(
            path,
            reason=reason,
        )

        return {
            "status": "ARCHIVED_FOR_REBUILD",
            "path": str(path),
            "size_bytes": inspection[
                "size_bytes"
            ],
            "valid_json": inspection[
                "valid_json"
            ],
            "reason": reason.upper(),
            "archive": str(archived),
        }

    def _archive(
        self,
        source: Path,
        *,
        reason: str,
    ) -> Path:
        self.archive_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        timestamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        destination = (
            self.archive_dir
            / (
                f"{source.stem}."
                f"{reason}."
                f"{timestamp}"
                f"{source.suffix}"
            )
        )
        counter = 1

        while destination.exists():
            destination = (
                self.archive_dir
                / (
                    f"{source.stem}."
                    f"{reason}."
                    f"{timestamp}."
                    f"{counter}"
                    f"{source.suffix}"
                )
            )
            counter += 1

        shutil.move(
            str(source),
            str(destination),
        )

        return destination

    @staticmethod
    def _is_valid_json(
        path: Path,
    ) -> bool:
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                json.load(file)
            return True
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ):
            return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migracja danych runtime JARVIS OS."
        )
    )
    parser.add_argument(
        "--project-root",
        default=None,
    )
    parser.add_argument(
        "--repair-cache",
        action="store_true",
    )
    parser.add_argument(
        "--max-cache-mb",
        type=int,
        default=10,
    )
    arguments = parser.parse_args()

    result = RuntimeDataMigrator(
        project_root=arguments.project_root,
    ).run(
        repair_cache=arguments.repair_cache,
        max_cache_bytes=(
            arguments.max_cache_mb
            * 1024
            * 1024
        ),
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

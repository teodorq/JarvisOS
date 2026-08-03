from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest

from app.core.runtime_migration import (
    RuntimeDataMigrator,
)


class AuditA232AiPathsRuntimeTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(
            __file__
        ).resolve().parents[1]

    def test_active_ai_has_no_fixed_root_literal(self) -> None:
        offenders: list[str] = []

        for path in (
            self.project_root / "app/ai"
        ).rglob("*.py"):
            source = path.read_text(
                encoding="utf-8"
            )

            if (
                "C:/JarvisAI" in source
                or "C:\\\\JarvisAI" in source
            ):
                offenders.append(
                    str(
                        path.relative_to(
                            self.project_root
                        )
                    )
                )

        self.assertEqual(
            offenders,
            [],
        )

    def test_all_ai_files_parse(self) -> None:
        errors: list[str] = []

        for path in (
            self.project_root / "app/ai"
        ).rglob("*.py"):
            try:
                ast.parse(
                    path.read_text(
                        encoding="utf-8"
                    ),
                    filename=str(path),
                )
            except Exception as error:
                errors.append(
                    f"{path}: {error}"
                )

        self.assertEqual(
            errors,
            [],
            "\n".join(errors),
        )

    def test_legacy_memory_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = root / "memory.json"
            legacy.write_text(
                '{"notes": []}',
                encoding="utf-8",
            )

            result = RuntimeDataMigrator(
                root
            ).run()

            destination = (
                root / "data/memory.json"
            )

            self.assertTrue(
                destination.is_file()
            )
            self.assertFalse(
                legacy.exists()
            )
            self.assertEqual(
                result["migration"][0][
                    "status"
                ],
                "MIGRATED",
            )

    def test_duplicate_legacy_file_is_archived(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = (
                root / "data/memory.json"
            )
            destination.parent.mkdir(
                parents=True
            )
            destination.write_text(
                '{"current": true}',
                encoding="utf-8",
            )
            legacy = root / "memory.json"
            legacy.write_text(
                '{"legacy": true}',
                encoding="utf-8",
            )

            RuntimeDataMigrator(
                root
            ).run()

            self.assertFalse(
                legacy.exists()
            )
            self.assertTrue(
                list(
                    (
                        root
                        / "archive/runtime_migration"
                    ).glob(
                        "memory.duplicate.*.json"
                    )
                )
            )

    def test_oversized_cache_is_archived(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = (
                root
                / "data/cache/symbol_index.json"
            )
            cache.parent.mkdir(
                parents=True
            )
            cache.write_text(
                json.dumps(
                    {
                        "payload": "x" * 500,
                    }
                ),
                encoding="utf-8",
            )

            result = RuntimeDataMigrator(
                root
            ).repair_symbol_cache(
                max_bytes=100
            )

            self.assertEqual(
                result["status"],
                "ARCHIVED_FOR_REBUILD",
            )
            self.assertFalse(
                cache.exists()
            )
            self.assertEqual(
                result["reason"],
                "OVERSIZED",
            )

    def test_invalid_cache_is_archived(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = (
                root
                / "data/cache/symbol_index.json"
            )
            cache.parent.mkdir(
                parents=True
            )
            cache.write_text(
                "{broken",
                encoding="utf-8",
            )

            result = RuntimeDataMigrator(
                root
            ).repair_symbol_cache()

            self.assertEqual(
                result["reason"],
                "INVALID",
            )
            self.assertFalse(
                cache.exists()
            )

    def test_valid_small_cache_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = (
                root
                / "data/cache/symbol_index.json"
            )
            cache.parent.mkdir(
                parents=True
            )
            cache.write_text(
                '{"classes": []}',
                encoding="utf-8",
            )

            result = RuntimeDataMigrator(
                root
            ).repair_symbol_cache(
                max_bytes=1000
            )

            self.assertEqual(
                result["status"],
                "READY",
            )
            self.assertTrue(
                cache.exists()
            )


if __name__ == "__main__":
    unittest.main()

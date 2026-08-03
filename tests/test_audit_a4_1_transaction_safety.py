from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from app.autodev.backup_bundle import BackupBundleManager
from app.autodev.change_transaction import ChangeTransaction
from app.autodev.developer_executor import DeveloperExecutor
from app.autodev.execution_result import ExecutionResult


class FailingSecondWriteExecutor(DeveloperExecutor):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.write_count = 0

    def _atomic_write_text(
        self,
        file_path: Path,
        content: str,
    ) -> None:
        self.write_count += 1

        if self.write_count == 2:
            raise OSError(
                "symulowana awaria drugiego zapisu"
            )

        super()._atomic_write_text(
            file_path,
            content,
        )


class AuditA41TransactionSafetyTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp_dir.name
        ).resolve()
        self.first = self.root / "app/first.py"
        self.second = self.root / "app/second.py"
        self.first.parent.mkdir(
            parents=True
        )
        self.first.write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )
        self.second.write_text(
            "VALUE = 2\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def manager(self) -> BackupBundleManager:
        return BackupBundleManager(
            project_root=self.root
        )

    def transaction(self) -> ChangeTransaction:
        transaction = ChangeTransaction(
            goal="Bezpieczna zmiana",
            target="app",
        )
        transaction.add_change(
            str(self.first),
            "VALUE = 1\n",
            "VALUE = 10\n",
        )
        transaction.add_change(
            str(self.second),
            "VALUE = 2\n",
            "VALUE = 20\n",
        )
        return transaction

    def test_backup_manifest_contains_hash_and_relative_paths(
        self,
    ) -> None:
        manifest = self.manager().create_bundle(
            [
                str(self.first),
                str(self.second),
            ],
            goal="audit",
        )

        self.assertEqual(
            manifest["version"],
            2,
        )
        self.assertEqual(
            manifest["errors"],
            [],
        )
        self.assertEqual(
            len(manifest["files"]),
            2,
        )

        for item in manifest["files"]:
            self.assertTrue(
                item["relative_path"].startswith(
                    "app/"
                )
            )
            self.assertEqual(
                len(item["sha256"]),
                64,
            )
            self.assertFalse(
                Path(
                    item["backup_relative"]
                ).is_absolute()
            )

    def test_restore_rejects_target_outside_project(
        self,
    ) -> None:
        manager = self.manager()
        manifest = manager.create_bundle(
            [str(self.first)]
        )
        manifest_path = (
            Path(manifest["bundle_path"])
            / "manifest.json"
        )
        data = json.loads(
            manifest_path.read_text(
                encoding="utf-8",
            )
        )
        data["files"][0][
            "relative_path"
        ] = "../outside.py"
        manifest_path.write_text(
            json.dumps(data),
            encoding="utf-8",
        )
        original = self.first.read_text(
            encoding="utf-8",
        )

        result = manager.restore_bundle(
            manifest["bundle_path"]
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            self.first.read_text(
                encoding="utf-8",
            ),
            original,
        )

    def test_restore_rejects_tampered_backup_hash(
        self,
    ) -> None:
        manager = self.manager()
        manifest = manager.create_bundle(
            [str(self.first)]
        )
        backup = Path(
            manifest["files"][0]["backup"]
        )
        backup.write_text(
            "TAMPERED = True\n",
            encoding="utf-8",
        )
        self.first.write_text(
            "VALUE = 999\n",
            encoding="utf-8",
        )

        result = manager.restore_bundle(
            manifest["bundle_path"]
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            self.first.read_text(
                encoding="utf-8",
            ),
            "VALUE = 999\n",
        )

    def test_bundle_outside_backup_root_is_rejected(
        self,
    ) -> None:
        manager = self.manager()
        outside = self.root / "other"
        outside.mkdir()
        (outside / "manifest.json").write_text(
            '{"files": []}',
            encoding="utf-8",
        )

        result = manager.restore_bundle(
            str(outside)
        )

        self.assertFalse(
            result["success"]
        )
        self.assertIn(
            "poza",
            result["errors"][0],
        )

    def test_preflight_prevents_partial_write(
        self,
    ) -> None:
        transaction = self.transaction()
        self.second.write_text(
            "EXTERNAL = 1\n",
            encoding="utf-8",
        )
        executor = DeveloperExecutor(
            project_root=self.root,
            run_tests=False,
        )

        result = executor.execute(
            transaction,
            auto_rollback=False,
        )

        self.assertFalse(
            result.success
        )
        self.assertEqual(
            self.first.read_text(
                encoding="utf-8",
            ),
            "VALUE = 1\n",
        )
        self.assertEqual(
            self.second.read_text(
                encoding="utf-8",
            ),
            "EXTERNAL = 1\n",
        )

    def test_write_failure_restores_all_files(
        self,
    ) -> None:
        transaction = self.transaction()
        executor = FailingSecondWriteExecutor(
            project_root=self.root,
            run_tests=False,
        )

        result = executor.execute(
            transaction,
            auto_rollback=True,
        )

        self.assertFalse(
            result.success
        )
        self.assertTrue(
            result.data["rollback"]["success"]
        )
        self.assertEqual(
            self.first.read_text(
                encoding="utf-8",
            ),
            "VALUE = 1\n",
        )
        self.assertEqual(
            self.second.read_text(
                encoding="utf-8",
            ),
            "VALUE = 2\n",
        )


    def test_failed_primary_rollback_uses_safe_fallback(
        self,
    ) -> None:
        transaction = self.transaction()
        executor = FailingSecondWriteExecutor(
            project_root=self.root,
            run_tests=False,
        )
        executor.rollback_manager.rollback = lambda transaction: (
            ExecutionResult(
                success=False,
                step_name="rollback",
                message="symulowana awaria rollback managera",
                errors=[
                    "symulowana awaria",
                ],
            )
        )

        result = executor.execute(
            transaction,
            auto_rollback=True,
        )

        self.assertFalse(
            result.success
        )
        self.assertTrue(
            result.data["rollback"]["success"]
        )
        self.assertTrue(
            result.data["rollback"]["data"][
                "fallback"
            ]
        )
        self.assertEqual(
            self.first.read_text(
                encoding="utf-8",
            ),
            "VALUE = 1\n",
        )
        self.assertEqual(
            self.second.read_text(
                encoding="utf-8",
            ),
            "VALUE = 2\n",
        )

    def test_backup_root_is_inside_selected_project(
        self,
    ) -> None:
        manager = self.manager()

        manager.backup_root.relative_to(
            self.root
        )
        self.assertEqual(
            manager.backup_root,
            self.root
            / "data/backups/autodev",
        )

    def test_symlink_escape_is_rejected(
        self,
    ) -> None:
        outside_dir = Path(
            self.temp_dir.name
        ).parent / (
            Path(self.temp_dir.name).name
            + "_outside"
        )
        outside_dir.mkdir(
            exist_ok=True
        )
        outside_file = (
            outside_dir / "outside.py"
        )
        outside_file.write_text(
            "VALUE = 5\n",
            encoding="utf-8",
        )
        link = self.root / "app/link.py"

        try:
            link.symlink_to(
                outside_file
            )
        except (
            OSError,
            NotImplementedError,
        ):
            self.skipTest(
                "System nie pozwala utworzyć symlinka."
            )

        transaction = ChangeTransaction(
            goal="Symlink test"
        )
        transaction.add_change(
            str(link),
            "VALUE = 5\n",
            "VALUE = 6\n",
        )
        executor = DeveloperExecutor(
            project_root=self.root,
            run_tests=False,
        )

        result = executor.execute(
            transaction
        )

        self.assertFalse(
            result.success
        )
        self.assertEqual(
            result.step_name,
            "path_validation",
        )
        self.assertEqual(
            outside_file.read_text(
                encoding="utf-8",
            ),
            "VALUE = 5\n",
        )
        link.unlink(
            missing_ok=True
        )
        outside_file.unlink(
            missing_ok=True
        )
        outside_dir.rmdir()


if __name__ == "__main__":
    unittest.main()

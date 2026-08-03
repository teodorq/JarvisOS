from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from app.ai.brain_response_formatter import (
    BrainResponseFormatter,
)
from app.ai.software_engineer import (
    AutonomousSoftwareEngineerController,
    FeatureCodeGenerator,
    FeaturePlanner,
    MultiFileFeatureExecutor,
)
from app.autodev.execution_result import ExecutionResult
from app.autodev.transaction_builder import TransactionBuilder


class FakeMultiFileExecutor:

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, blueprint, **kwargs):
        self.calls.append(
            {
                "blueprint": blueprint,
                **kwargs,
            }
        )
        return {
            "success": True,
            "status": "PREVIEW_READY",
            "files_count": len(
                blueprint.files
            ),
            "errors": [],
        }


class B5152MultiFileExecutionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp_dir.name
        ).resolve()
        (self.root / "app").mkdir()
        (self.root / "app/__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        (self.root / "tests").mkdir()
        (self.root / "tests/__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        self.blueprint = FeaturePlanner().plan(
            "Dodaj system powiadomień",
            feature_name="NotificationCenter",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def executor(self) -> MultiFileFeatureExecutor:
        executor = MultiFileFeatureExecutor(
            self.root
        )
        validator = (
            executor.developer_controller
            .executor
            .validator
        )
        validator.validate_files = lambda files: ExecutionResult(
            success=True,
            step_name="validate_files",
            message="OK",
        )
        validator.run_import_test = lambda: ExecutionResult(
            success=True,
            step_name="import",
            message="OK",
        )
        validator.run_test_suite = lambda **kwargs: ExecutionResult(
            success=True,
            step_name="tests",
            message="OK",
        )
        return executor

    def test_generator_builds_all_syntax_valid_files(self) -> None:
        replacements = FeatureCodeGenerator().generate(
            self.blueprint
        )

        self.assertEqual(
            list(replacements),
            [
                self.blueprint.file_map()[file_id].relative_path
                for file_id in self.blueprint.creation_order
            ],
        )
        self.assertEqual(
            len(replacements),
            len(self.blueprint.files),
        )

        for path, content in replacements.items():
            ast.parse(
                content,
                filename=path,
            )

        self.assertIn(
            "NotificationCenterService",
            replacements[
                "app/features/notification_center/service.py"
            ],
        )

    def test_transaction_builder_supports_new_files(self) -> None:
        first = self.root / "app/one.py"
        second = self.root / "app/two.py"
        transaction = (
            TransactionBuilder()
            .build_multi_file_replacement(
                goal="Utwórz dwa pliki",
                target="app",
                replacements={
                    str(first): "VALUE = 1\n",
                    str(second): "VALUE = 2\n",
                },
                allow_create=True,
            )
        )

        valid, errors = transaction.validate()

        self.assertTrue(
            valid,
            errors,
        )
        self.assertEqual(
            transaction.created_files(),
            [
                str(first),
                str(second),
            ],
        )
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())

    def test_preview_does_not_create_placeholder_files(self) -> None:
        result = self.executor().execute(
            self.blueprint,
            auto_approve=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PREVIEW_READY",
        )
        self.assertTrue(
            all(
                not (self.root / path).exists()
                for path in result["files"]
            )
        )

    def test_execution_creates_all_files_in_one_transaction(self) -> None:
        executor = self.executor()
        result = executor.execute(
            self.blueprint,
            auto_approve=True,
        )

        self.assertTrue(
            result["success"],
            result["errors"],
        )
        self.assertEqual(
            result["status"],
            "COMPLETED",
        )
        self.assertEqual(
            result["files_count"],
            len(self.blueprint.files),
        )
        self.assertTrue(
            all(
                (self.root / path).is_file()
                for path in result["files"]
            )
        )
        transaction = (
            executor.developer_controller
            .executor
            .last_transaction
        )
        self.assertEqual(
            len(transaction.changes),
            len(self.blueprint.files),
        )
        self.assertTrue(
            all(
                change.operation == "create"
                for change in transaction.changes
            )
        )

    def test_failed_validation_removes_every_new_file(self) -> None:
        executor = self.executor()
        executor.developer_controller.executor.validator.run_import_test = (
            lambda: ExecutionResult(
                success=False,
                step_name="import",
                message="Błąd importu",
                errors=[
                    "symulowany błąd",
                ],
            )
        )

        result = executor.execute(
            self.blueprint,
            auto_approve=True,
            auto_rollback=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "FAILED_AND_ROLLED_BACK",
        )
        self.assertTrue(
            all(
                not (self.root / path).exists()
                for path in result["files"]
            )
        )

    def test_existing_target_is_blocked_by_default(self) -> None:
        existing = (
            self.root
            / "app/features/notification_center/models.py"
        )
        existing.parent.mkdir(
            parents=True
        )
        existing.write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )

        result = self.executor().execute(
            self.blueprint,
            auto_approve=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "FEATURE_VALIDATION_FAILED",
        )
        self.assertIn(
            "Target już istnieje",
            " ".join(result["errors"]),
        )
        self.assertEqual(
            existing.read_text(
                encoding="utf-8"
            ),
            "VALUE = 1\n",
        )

    def test_controller_routes_multi_file_feature(self) -> None:
        fake_executor = FakeMultiFileExecutor()
        controller = AutonomousSoftwareEngineerController(
            project_root=self.root,
            multi_file_executor=fake_executor,
        )

        result = controller.handle(
            (
                "Stwórz funkcjonalność autonomicznie "
                "system powiadomień"
            ),
            {
                "feature_name": "NotificationCenter",
                "auto_execute": True,
                "auto_approve": False,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PREVIEW_READY",
        )
        self.assertEqual(
            len(fake_executor.calls),
            1,
        )
        self.assertTrue(
            result["feature_blueprint"][
                "metadata"
            ]["multi_file"]
        )

    def test_formatter_reports_multi_file_preview(self) -> None:
        response = {
            "success": True,
            "status": "PREVIEW_READY",
            "feature_blueprint": self.blueprint.to_dict(),
            "execution": {
                "files_count": len(
                    self.blueprint.files
                ),
            },
        }

        text = (
            BrainResponseFormatter()
            ._format_software_engineer_response(
                response
            )
        )

        self.assertIn(
            "NotificationCenter",
            text,
        )
        self.assertIn(
            "Pliki w transakcji",
            text,
        )
        self.assertIn(
            "gotowy do akceptacji",
            text,
        )


if __name__ == "__main__":
    unittest.main()

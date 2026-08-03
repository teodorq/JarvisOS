from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer import (
    AutonomousSoftwareEngineerController,
    FeaturePlanner,
    MultiFileFeatureExecutor,
    MultiFileFeatureVerifier,
    MultiFileFeatureWorkflow,
    MultiFileRunStore,
)
from app.autodev.execution_result import ExecutionResult


class ForcedFailureVerifier:

    def verify(self, blueprint, execution, **kwargs):
        status = str(
            execution.get(
                "status",
                "UNKNOWN",
            )
        ).upper()

        if "ROLLED_BACK" in status:
            return {
                "success": True,
                "status": "VERIFIED",
                "execution_status": status,
                "checked_files": [],
                "errors": [],
            }

        return {
            "success": False,
            "status": "VERIFICATION_FAILED",
            "execution_status": status,
            "checked_files": [],
            "errors": [
                "symulowany błąd weryfikacji końcowej",
            ],
        }


class FakeIntegratedWorkflow:

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, objective, **kwargs):
        self.calls.append(
            {
                "objective": objective,
                **kwargs,
            }
        )
        return {
            "run_id": "run-test",
            "success": True,
            "status": "COMPLETED",
            "objective": objective,
            "feature_blueprint": {
                "feature_name": "DemoFeature",
                "package_path": "app/features/demo_feature",
                "files": [],
                "metadata": {
                    "multi_file": True,
                },
            },
            "execution": {
                "files_count": 0,
            },
            "verification": {
                "success": True,
                "status": "VERIFIED",
            },
            "report_path": "data/autodev/multi_file_feature_runs.json",
            "errors": [],
        }


class B5153IntegratedMultiFileWorkflowTests(unittest.TestCase):

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

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def real_executor(self) -> MultiFileFeatureExecutor:
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

    def workflow(self, *, verifier=None) -> MultiFileFeatureWorkflow:
        executor = self.real_executor()
        return MultiFileFeatureWorkflow(
            self.root,
            feature_executor=executor,
            verifier=(
                verifier
                or MultiFileFeatureVerifier(
                    self.root
                )
            ),
        )

    def test_full_workflow_creates_verifies_and_persists_run(self) -> None:
        workflow = self.workflow()
        result = workflow.run(
            "Dodaj system alertów",
            feature_name="AlertCenter",
            auto_execute=True,
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
            result["verification"]["status"],
            "VERIFIED",
        )
        self.assertTrue(
            result["run_id"]
        )
        self.assertTrue(
            Path(
                result["report_path"]
            ).is_file()
        )
        stored = workflow.get_run(
            result["run_id"]
        )
        self.assertIsNotNone(stored)
        self.assertEqual(
            stored["status"],
            "COMPLETED",
        )

    def test_preview_is_reported_without_creating_files(self) -> None:
        workflow = self.workflow()
        result = workflow.run(
            "Dodaj system powiadomień",
            feature_name="NotificationCenter",
            auto_execute=True,
            auto_approve=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PREVIEW_READY",
        )
        self.assertEqual(
            result["verification"]["status"],
            "VERIFIED",
        )
        self.assertTrue(
            all(
                not (
                    self.root
                    / item["relative_path"]
                ).exists()
                for item in result[
                    "feature_blueprint"
                ]["files"]
            )
        )

    def test_plan_only_run_is_persisted(self) -> None:
        workflow = self.workflow()
        result = workflow.run(
            "Dodaj moduł raportów",
            feature_name="ReportCenter",
            auto_execute=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "FEATURE_BLUEPRINT_READY",
        )
        self.assertEqual(
            result["verification"]["status"],
            "NOT_EXECUTED",
        )
        self.assertIsNotNone(
            workflow.get_run(
                result["run_id"]
            )
        )

    def test_post_verification_failure_rolls_back_every_file(self) -> None:
        workflow = self.workflow(
            verifier=ForcedFailureVerifier()
        )
        result = workflow.run(
            "Dodaj system zdarzeń",
            feature_name="EventCenter",
            auto_execute=True,
            auto_approve=True,
            auto_rollback=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "POST_VERIFY_FAILED_AND_ROLLED_BACK",
        )
        self.assertTrue(
            result["rollback"]["success"]
        )
        self.assertTrue(
            all(
                not (
                    self.root
                    / item["relative_path"]
                ).exists()
                for item in result[
                    "feature_blueprint"
                ]["files"]
            )
        )

    def test_verifier_detects_missing_file_after_completion(self) -> None:
        blueprint = FeaturePlanner().plan(
            "Dodaj audyt logów",
            feature_name="AuditLog",
        )
        verification = MultiFileFeatureVerifier(
            self.root
        ).verify(
            blueprint,
            {
                "status": "COMPLETED",
                "files": [
                    item.relative_path
                    for item in blueprint.files
                ],
            },
        )

        self.assertFalse(
            verification["success"]
        )
        self.assertIn(
            "Brak pliku",
            " ".join(
                verification["errors"]
            ),
        )

    def test_verifier_detects_invalid_python_syntax(self) -> None:
        blueprint = FeaturePlanner().plan(
            "Dodaj centrum danych",
            feature_name="DataCenter",
        )

        for item in blueprint.files:
            target = self.root / item.relative_path
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            target.write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

        broken = (
            self.root
            / blueprint.files[0].relative_path
        )
        broken.write_text(
            "def broken(:\n",
            encoding="utf-8",
        )
        verification = MultiFileFeatureVerifier(
            self.root
        ).verify(
            blueprint,
            {
                "status": "COMPLETED",
                "files": [
                    item.relative_path
                    for item in blueprint.files
                ],
            },
        )

        self.assertFalse(
            verification["success"]
        )
        self.assertIn(
            "SyntaxError",
            " ".join(
                verification["errors"]
            ),
        )

    def test_run_store_is_atomic_bounded_and_returns_recent(self) -> None:
        store = MultiFileRunStore(
            self.root,
            max_records=10,
        )

        for index in range(12):
            store.save(
                {
                    "run_id": f"run-{index}",
                    "status": "COMPLETED",
                }
            )

        recent = store.list_recent(
            limit=20
        )
        self.assertEqual(
            len(recent),
            10,
        )
        self.assertEqual(
            recent[0]["run_id"],
            "run-11",
        )
        self.assertIsNone(
            store.get("run-0")
        )

    def test_controller_routes_through_integrated_workflow(self) -> None:
        fake_workflow = FakeIntegratedWorkflow()
        controller = AutonomousSoftwareEngineerController(
            project_root=self.root,
            multi_file_workflow=fake_workflow,
        )
        result = controller.handle(
            (
                "Stwórz funkcjonalność autonomicznie "
                "centrum zdarzeń"
            ),
            {
                "feature_name": "EventCenter",
                "auto_execute": True,
                "auto_approve": True,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["run_id"],
            "run-test",
        )
        self.assertEqual(
            len(fake_workflow.calls),
            1,
        )

    def test_formatter_reports_run_verification_and_report_path(self) -> None:
        text = BrainResponseFormatter()._format_software_engineer_response(
            {
                "success": True,
                "status": "COMPLETED",
                "run_id": "run-123",
                "feature_blueprint": {
                    "feature_name": "DemoFeature",
                    "package_path": "app/features/demo_feature",
                    "files": [
                        {},
                        {},
                    ],
                },
                "execution": {
                    "files_count": 2,
                },
                "verification": {
                    "status": "VERIFIED",
                },
                "report_path": (
                    "data/autodev/multi_file_feature_runs.json"
                ),
            }
        )

        self.assertIn("run-123", text)
        self.assertIn("VERIFIED", text)
        self.assertIn("Raport przebiegów", text)
        self.assertIn("jedna transakcja", text)

    def test_controller_remains_below_audit_limit(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "app/ai/software_engineer/"
            "autonomous_software_engineer.py"
        ).read_text(
            encoding="utf-8"
        )
        self.assertLess(
            len(source.splitlines()),
            440,
        )
        ast.parse(source)


if __name__ == "__main__":
    unittest.main()

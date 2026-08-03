"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_diagnostics_analyzer import (
    AutonomousDiagnosticsAnalyzer,
)
from app.ai.software_engineer.autonomous_diagnostics_collector import (
    AutonomousDiagnosticsCollector,
)
from app.ai.software_engineer.autonomous_diagnostics_models import (
    AutonomousDiagnostic,
)
from app.ai.software_engineer.autonomous_diagnostics_service import (
    AutonomousDiagnosticsService,
)
from app.ai.software_engineer.autonomous_diagnostics_store import (
    AutonomousDiagnosticsStore,
)
from app.ai.software_engineer.autonomous_self_repair import (
    AutonomousSelfRepair,
)
from app.ai.software_engineer.full_autonomy_store import FullAutonomyStore
from app.ai.software_engineer.full_autonomy_workflow import FullAutonomyWorkflow
from app.ai.software_engineer.long_running_autonomy_models import (
    LongRunningJob,
)
from app.ai.software_engineer.long_running_autonomy_service import (
    LongRunningAutonomyService,
)
from app.ai.software_engineer.long_running_autonomy_store import (
    LongRunningAutonomyStore,
)
from app.ai.software_engineer.long_running_resource_guard import (
    LongRunningResourceGuard,
)
from app.ai.software_engineer.software_engineer_diagnostics_formatter import (
    format_autonomous_diagnostics_response,
)
from app.ai.software_engineer.software_engineer_diagnostics_router import (
    SoftwareEngineerDiagnosticsRouter,
)
from app.gui.command_safety import is_read_only_learning_command
from tools.migrate_b54_diagnostics import migrate


NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


class FakeWorkflow:
    def __init__(self, responses: list[dict] | None = None) -> None:
        self.responses = list(responses or [{
            "success": True,
            "status": "FULL_AUTONOMY_COMPLETED",
            "autonomy_run_id": "autonomy-completed",
            "errors": [],
        }])
        self.run_calls: list[tuple[str, dict]] = []
        self.execute_calls: list[tuple[str, dict]] = []

    def _next(self) -> dict:
        if len(self.responses) > 1:
            return dict(self.responses.pop(0))
        return dict(self.responses[0])

    def run(self, objective: str, *, context: dict | None = None) -> dict:
        self.run_calls.append((objective, dict(context or {})))
        return self._next()

    def execute(self, run_id: str, *, context: dict | None = None) -> dict:
        self.execute_calls.append((run_id, dict(context or {})))
        return self._next()

    def status(self, run_id: str) -> dict:
        return {
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": run_id,
            "errors": [],
        }


class RaisingWorkflow(FakeWorkflow):
    def run(self, objective: str, *, context: dict | None = None) -> dict:
        raise RuntimeError("executor exploded")


class B54AutonomousDiagnosticsTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def long_service(
        self,
        workflow: FakeWorkflow | None = None,
    ) -> LongRunningAutonomyService:
        guard = LongRunningResourceGuard(
            self.root,
            sample_provider=lambda: {
                "cpu_percent": 10.0,
                "memory_percent": 20.0,
                "disk_free_gb": 100.0,
                "on_ac_power": True,
            },
        )
        return LongRunningAutonomyService(
            self.root,
            workflow=workflow or FakeWorkflow(),
            resource_guard=guard,
            clock=lambda: NOW,
        )

    @staticmethod
    def approval_response() -> dict:
        return {
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": "autonomy-approval",
            "errors": [],
            "execution": {
                "current_campaign_id": "campaign-one",
                "current_stage_id": "feature-create",
            },
            "portfolio": {
                "campaigns": [{
                    "campaign_id": "campaign-one",
                    "metadata": {"estimated_risk": 3.2},
                    "stages": [{
                        "stage_id": "feature-create",
                        "status": "PREVIEW_READY",
                    }],
                }],
            },
        }

    def test_model_round_trip_preserves_diagnostic_fields(self) -> None:
        original = AutonomousDiagnostic(
            job_id="longrun-model",
            category="VALIDATION_FAILED",
            traceback="trace",
            files=["app/demo.py"],
        )

        restored = AutonomousDiagnostic.from_dict(original.to_dict())

        self.assertEqual(restored.job_id, "longrun-model")
        self.assertEqual(restored.category, "VALIDATION_FAILED")
        self.assertEqual(restored.traceback, "trace")
        self.assertEqual(restored.files, ["app/demo.py"])

    def test_store_persists_bounded_diagnostics(self) -> None:
        store = AutonomousDiagnosticsStore(self.root, max_records=50)
        for index in range(55):
            store.save_diagnostic(AutonomousDiagnostic(
                diagnostic_id=f"diagnostic-{index}",
                job_id="longrun-bounded",
                root_cause="x" * 7000,
            ))

        payload = store.load()

        self.assertEqual(len(payload["records"]), 50)
        self.assertNotIn("diagnostic-0", payload["records"])
        self.assertLessEqual(
            len(payload["records"]["diagnostic-54"]["root_cause"]),
            5000,
        )

    def test_store_persists_repair_history_and_summary(self) -> None:
        store = AutonomousDiagnosticsStore(self.root)
        store.save_diagnostic(AutonomousDiagnostic(
            diagnostic_id="diagnostic-one",
            category="APPROVAL_REQUIRED",
            repairable=True,
        ))
        store.save_repair({
            "repair_id": "repair-one",
            "status": "AUTONOMOUS_REPAIR_STATE_RESET",
            "job_id": "longrun-one",
            "success": True,
        })

        summary = store.summary()

        self.assertEqual(summary["records"], 1)
        self.assertEqual(summary["repairs"], 1)
        self.assertEqual(summary["repairable"], 1)
        self.assertEqual(store.list_repairs()[0]["repair_id"], "repair-one")

    def test_collector_redacts_project_root_and_secrets(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        store.save_job(LongRunningJob(
            job_id="longrun-redact",
            objective="diagnose",
        ))
        collector = AutonomousDiagnosticsCollector(
            self.root,
            long_running_store=store,
        )

        snapshot = collector.collect_job(
            "longrun-redact",
            response={
                "status": "FAILED",
                "errors": [
                    f"Path {self.root / 'app' / 'demo.py'} api_key=secret-value"
                ],
            },
        )
        text = str(snapshot)

        self.assertNotIn(str(self.root), text)
        self.assertNotIn("secret-value", text)
        self.assertIn("<PROJECT_ROOT>", text)
        self.assertIn("<REDACTED>", text)

    def test_collector_extracts_traceback_streams_and_files(self) -> None:
        collector = AutonomousDiagnosticsCollector(self.root)
        evidence = collector.evidence({
            "status": "VALIDATION_FAILED",
            "traceback": "Traceback: boom",
            "stdout": "test output",
            "stderr": "syntax error",
            "changed_files": ["app/a.py", "app/b.py"],
        })

        self.assertIn("VALIDATION_FAILED", evidence["statuses"])
        self.assertIn("Traceback: boom", evidence["traceback"])
        self.assertIn("test output", evidence["stdout"])
        self.assertIn("syntax error", evidence["stderr"])
        self.assertEqual(evidence["files"], ["app/a.py", "app/b.py"])

    def test_analyzer_approval_precedes_attempt_and_cycle_symptoms(self) -> None:
        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            {
                "identifiers": {"job_id": "longrun-approval"},
                "campaigns": [{
                    "stages": [{
                        "stage_id": "feature-create",
                        "status": "PREVIEW_READY",
                    }],
                }],
            },
            {
                "statuses": [
                    "ATTEMPTS_EXHAUSTED",
                    "CYCLE_LIMIT",
                    "PREVIEW_READY",
                ],
                "errors": ["Przekroczono limit prób"],
                "current_stage_id": "feature-create",
            },
        )

        self.assertEqual(diagnostic.category, "APPROVAL_REQUIRED")
        self.assertEqual(diagnostic.repair_type, "ONE_TIME_APPROVAL")
        self.assertTrue(diagnostic.requires_approval)
        self.assertEqual(diagnostic.stage, "feature-create")

    def test_analyzer_classifies_validation_failure(self) -> None:
        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            {"identifiers": {}},
            {
                "statuses": ["FULL_AUTONOMY_VALIDATION_FAILED"],
                "errors": ["2 tests failed"],
            },
        )

        self.assertEqual(diagnostic.category, "VALIDATION_FAILED")
        self.assertEqual(diagnostic.severity, "ERROR")
        self.assertTrue(diagnostic.repairable)

    def test_analyzer_classifies_transient_exception_as_retryable(self) -> None:
        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            {"identifiers": {}},
            {
                "statuses": ["LONG_RUNNING_WORKFLOW_EXCEPTION"],
                "errors": ["TimeoutError: connection temporarily busy"],
                "traceback": "Traceback...",
            },
        )

        self.assertEqual(diagnostic.category, "EXECUTION_EXCEPTION")
        self.assertTrue(diagnostic.retryable)
        self.assertEqual(diagnostic.repair_type, "RESET_TRANSIENT")

    def test_analyzer_classifies_target_conflict(self) -> None:
        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            {"identifiers": {}},
            {
                "statuses": ["FEATURE_PLAN_FAILED"],
                "errors": ["Target już istnieje: app/demo.py"],
            },
        )

        self.assertEqual(diagnostic.category, "TARGET_CONFLICT")
        self.assertFalse(diagnostic.repairable)

    def test_analyzer_does_not_blindly_repair_attempts_exhausted(self) -> None:
        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            {"identifiers": {}},
            {
                "statuses": ["LONG_RUNNING_JOB_ATTEMPTS_EXHAUSTED"],
                "errors": ["Przekroczono limit prób"],
            },
        )

        self.assertEqual(diagnostic.category, "ATTEMPTS_EXHAUSTED")
        self.assertFalse(diagnostic.repairable)
        self.assertEqual(diagnostic.repair_type, "NONE")

    def test_service_diagnoses_job_and_persists_report(self) -> None:
        long_store = LongRunningAutonomyStore(self.root)
        long_store.save_job(LongRunningJob(
            job_id="longrun-service",
            objective="goal",
        ))
        service = AutonomousDiagnosticsService(
            self.root,
            long_running_store=long_store,
        )

        result = service.diagnose_job(
            "longrun-service",
            response=self.approval_response(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["diagnostic"]["category"],
            "APPROVAL_REQUIRED",
        )
        self.assertTrue(Path(result["report_path"]).is_file())
        self.assertEqual(service.status()["summary"]["records"], 1)

    def test_service_recent_can_filter_category(self) -> None:
        service = AutonomousDiagnosticsService(self.root)
        service.store.save_diagnostic(AutonomousDiagnostic(
            diagnostic_id="diagnostic-a",
            category="VALIDATION_FAILED",
        ))
        service.store.save_diagnostic(AutonomousDiagnostic(
            diagnostic_id="diagnostic-b",
            category="APPROVAL_REQUIRED",
        ))

        result = service.recent(category="approval_required")

        self.assertEqual(len(result["diagnostics"]), 1)
        self.assertEqual(
            result["diagnostics"][0]["category"],
            "APPROVAL_REQUIRED",
        )

    def test_self_repair_one_time_approval_is_bounded(self) -> None:
        long_store = LongRunningAutonomyStore(self.root)
        long_store.save_job(LongRunningJob(
            job_id="longrun-repair",
            objective="goal",
            state="WAITING_APPROVAL",
            attempts=3,
            autonomy_run_id="autonomy-existing",
        ))
        diagnostics_store = AutonomousDiagnosticsStore(self.root)
        repair = AutonomousSelfRepair(
            self.root,
            long_running_store=long_store,
            diagnostics_store=diagnostics_store,
            clock=lambda: NOW,
        ).repair_job(
            "longrun-repair",
            AutonomousDiagnostic(
                diagnostic_id="diagnostic-repair",
                repair_type="ONE_TIME_APPROVAL",
                metadata={"maximum_risk": 3.2},
            ).to_dict(),
        )

        saved = long_store.get_job("longrun-repair")
        self.assertTrue(repair["success"])
        self.assertEqual(saved["state"], "QUEUED")
        self.assertEqual(saved["attempts"], 0)
        self.assertEqual(saved["autonomy_run_id"], "autonomy-existing")
        self.assertTrue(
            saved["execution_context"]["_b54_one_time_auto_approve"]
        )
        self.assertFalse(long_store.policy()["auto_approve"])

    def test_self_repair_blocks_high_risk_one_time_approval(self) -> None:
        long_store = LongRunningAutonomyStore(self.root)
        long_store.save_job(LongRunningJob(
            job_id="longrun-risk",
            objective="goal",
            state="WAITING_APPROVAL",
        ))
        repair = AutonomousSelfRepair(
            self.root,
            long_running_store=long_store,
        ).repair_job(
            "longrun-risk",
            AutonomousDiagnostic(
                diagnostic_id="diagnostic-risk",
                repair_type="ONE_TIME_APPROVAL",
                metadata={"maximum_risk": 8.0},
            ).to_dict(),
        )

        self.assertFalse(repair["success"])
        self.assertEqual(repair["status"], "AUTONOMOUS_REPAIR_RISK_BLOCKED")
        self.assertEqual(
            long_store.get_job("longrun-risk")["state"],
            "WAITING_APPROVAL",
        )

    def test_self_repair_replan_clears_only_failed_plan_identity(self) -> None:
        long_store = LongRunningAutonomyStore(self.root)
        long_store.save_job(LongRunningJob(
            job_id="longrun-replan",
            objective="goal",
            state="FAILED",
            attempts=3,
            autonomy_run_id="autonomy-old",
        ))
        result = AutonomousSelfRepair(
            self.root,
            long_running_store=long_store,
        ).repair_job(
            "longrun-replan",
            AutonomousDiagnostic(
                diagnostic_id="diagnostic-replan",
                repair_type="REPLAN",
            ).to_dict(),
        )

        saved = long_store.get_job("longrun-replan")
        self.assertTrue(result["success"])
        self.assertEqual(saved["state"], "QUEUED")
        self.assertEqual(saved["autonomy_run_id"], "")
        self.assertEqual(
            saved["metadata"]["b54_previous_autonomy_run_id"],
            "autonomy-old",
        )

    def test_paused_preview_becomes_waiting_approval_without_retry_loop(self) -> None:
        service = self.long_service(FakeWorkflow([self.approval_response()]))
        job_id = service.enqueue("goal", context={"max_attempts": 3})["job_id"]

        service.tick(now=NOW)
        job = service.store.get_job(job_id)

        self.assertEqual(job["state"], "WAITING_APPROVAL")
        self.assertEqual(job["attempts"], 1)
        self.assertEqual(job["next_run_at"], "")
        self.assertEqual(
            job["last_result"]["diagnostic_category"],
            "APPROVAL_REQUIRED",
        )
        self.assertTrue(job["last_result"]["requires_approval"])

    def test_workflow_exception_is_saved_with_traceback(self) -> None:
        service = self.long_service(RaisingWorkflow())
        job_id = service.enqueue("goal", context={"max_attempts": 1})["job_id"]

        service.tick(now=NOW)
        diagnostic = service.diagnostics_service.store.latest_for_job(job_id)

        self.assertEqual(
            diagnostic["category"],
            "EXECUTION_EXCEPTION",
        )
        self.assertIn("RuntimeError", diagnostic["traceback"])
        self.assertIn("executor exploded", diagnostic["traceback"])

    def test_one_time_approval_is_passed_once_and_consumed(self) -> None:
        workflow = FakeWorkflow([{
            "success": True,
            "status": "FULL_AUTONOMY_COMPLETED",
            "autonomy_run_id": "autonomy-existing",
            "errors": [],
        }])
        service = self.long_service(workflow)
        job_id = service.enqueue("goal")["job_id"]
        job = service.store.get_job(job_id)
        job.update({
            "state": "QUEUED",
            "autonomy_run_id": "autonomy-existing",
            "execution_context": {
                "_b54_one_time_auto_approve": True,
                "_b54_repair_id": "repair-once",
            },
        })
        service.store.save_job(job)

        service.tick(now=NOW)
        saved = service.store.get_job(job_id)

        self.assertTrue(workflow.execute_calls[0][1]["auto_approve"])
        self.assertNotIn(
            "_b54_one_time_auto_approve",
            saved["execution_context"],
        )
        self.assertTrue(
            saved["metadata"]["b54_repair_approval_consumed"]
        )
        self.assertFalse(service.store.policy()["auto_approve"])

    def test_regular_execution_context_never_auto_approves(self) -> None:
        service = self.long_service()

        context = service._safe_execution_context({"auto_approve": True})

        self.assertFalse(context["auto_approve"])
        self.assertTrue(context["auto_rollback"])
        self.assertTrue(context["final_validation"])

    def test_router_routes_exact_polish_diagnostic_command(self) -> None:
        service = MagicMock()
        service.diagnose_job.return_value = {"status": "READY"}
        controller = SimpleNamespace(
            project_root=self.root,
            autonomous_diagnostics_service=service,
            _normalize=lambda value: " ".join(str(value).casefold().split()),
        )

        result = SoftwareEngineerDiagnosticsRouter().try_handle(
            controller,
            command=(
                "Wyjaśnij błąd zadania "
                "longrun-abc123"
            ),
            objective="",
            context={},
        )

        self.assertEqual(result["status"], "READY")
        service.diagnose_job.assert_called_once_with("longrun-abc123")

    def test_router_requires_job_id_for_repair(self) -> None:
        controller = SimpleNamespace(
            project_root=self.root,
            _normalize=lambda value: " ".join(str(value).casefold().split()),
        )

        result = SoftwareEngineerDiagnosticsRouter().try_handle(
            controller,
            command="Bezpieczna naprawa zadania",
            objective="",
            context={},
        )

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_DIAGNOSTIC_JOB_ID_REQUIRED",
        )

    def test_diagnostics_read_is_safe_but_repair_requires_confirmation(self) -> None:
        self.assertTrue(is_read_only_learning_command(
            "Wyjaśnij błąd zadania longrun-abc"
        ))
        self.assertFalse(is_read_only_learning_command(
            "Napraw zadanie longrun-abc"
        ))

    def test_formatter_reports_root_cause_and_traceback(self) -> None:
        text = format_autonomous_diagnostics_response({
            "status": "AUTONOMOUS_DIAGNOSTIC_READY",
            "operation": "autonomous_diagnostics",
            "diagnostic": {
                "diagnostic_id": "diagnostic-one",
                "job_id": "longrun-one",
                "category": "EXECUTION_EXCEPTION",
                "severity": "CRITICAL",
                "stage": "EXECUTE",
                "root_cause": "Runtime error",
                "traceback": "Traceback details",
                "repairable": False,
            },
        })

        self.assertIn("EXECUTION_EXCEPTION", text)
        self.assertIn("Runtime error", text)
        self.assertIn("Traceback details", text)

    def test_brain_formatter_routes_diagnostics_operation(self) -> None:
        text = BrainResponseFormatter()._format_software_engineer_response({
            "status": "AUTONOMOUS_DIAGNOSTICS_STATUS",
            "operation": "autonomous_diagnostics",
            "summary": {"records": 2, "repairs": 1, "repairable": 1},
        })

        self.assertIn("Diagnostyka autonomii", text)
        self.assertIn("raporty 2", text)

    def test_full_autonomy_planner_exception_preserves_traceback(self) -> None:
        planner = MagicMock()
        planner.plan.side_effect = ValueError("invalid objective")
        workflow = FullAutonomyWorkflow(
            self.root,
            planner=planner,
            portfolio_workflow=MagicMock(),
            optimizer=MagicMock(),
            director=MagicMock(),
            validator=MagicMock(),
            learning_engine=MagicMock(),
        )
        workflow.learning_engine.observe_run.return_value = {
            "success": True,
        }

        response = workflow.run("goal")

        self.assertEqual(response["status"], "FULL_AUTONOMY_PLANNING_FAILED")
        self.assertIn(
            "ValueError",
            response["diagnostics"]["last_traceback"],
        )
        self.assertIn(
            "invalid objective",
            response["diagnostics"]["last_traceback"],
        )

    def test_full_autonomy_validation_exception_returns_traceback(self) -> None:
        validator = MagicMock()
        validator.run_test_suite.side_effect = RuntimeError("tests crashed")
        workflow = FullAutonomyWorkflow(
            self.root,
            planner=MagicMock(),
            portfolio_workflow=MagicMock(),
            optimizer=MagicMock(),
            director=MagicMock(),
            validator=validator,
            learning_engine=MagicMock(),
        )

        result = workflow._validate({
            "plan": {"target_files": ["app/demo.py"]},
        })

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_VALIDATION_EXCEPTION",
        )
        self.assertIn("RuntimeError", result["traceback"])

    def test_migration_marks_existing_preview_failure_waiting_approval(self) -> None:
        long_store = LongRunningAutonomyStore(self.root)
        run_store = FullAutonomyStore(self.root)
        job = LongRunningJob(
            job_id="longrun-migrate",
            objective="goal",
            state="FAILED",
            attempts=3,
            autonomy_run_id="autonomy-migrate",
        )
        long_store.save_job(job)
        run_store.save({
            "run_id": "autonomy-migrate",
            "status": "FULL_AUTONOMY_PAUSED",
            "success": True,
            "portfolio": {
                "campaigns": [{
                    "campaign_id": "campaign-migrate",
                    "metadata": {"estimated_risk": 3.0},
                    "stages": [{
                        "stage_id": "feature-create",
                        "status": "PREVIEW_READY",
                    }],
                }],
            },
            "errors": [],
        })

        result = migrate(self.root)
        saved = long_store.get_job("longrun-migrate")

        self.assertTrue(result["success"])
        self.assertEqual(result["waiting_approval"], 1)
        self.assertEqual(saved["state"], "WAITING_APPROVAL")
        self.assertEqual(
            saved["last_result"]["diagnostic_category"],
            "APPROVAL_REQUIRED",
        )
        self.assertEqual(saved["attempts"], 3)

    def test_service_repair_reuses_exact_persisted_diagnostic(self) -> None:
        long_store = LongRunningAutonomyStore(self.root)
        diagnostics_store = AutonomousDiagnosticsStore(self.root)
        job = LongRunningJob(
            job_id="longrun-persisted",
            objective="goal",
            state="WAITING_APPROVAL",
            autonomy_run_id="autonomy-persisted",
        )
        job.last_result = {
            "diagnostic_id": "diagnostic-persisted",
            "diagnostic_category": "APPROVAL_REQUIRED",
            "requires_approval": True,
        }
        long_store.save_job(job)
        diagnostics_store.save_diagnostic(AutonomousDiagnostic(
            diagnostic_id="diagnostic-persisted",
            job_id="longrun-persisted",
            repairable=True,
            requires_approval=True,
            repair_type="ONE_TIME_APPROVAL",
            metadata={"maximum_risk": 2.0},
        ))
        service = AutonomousDiagnosticsService(
            self.root,
            store=diagnostics_store,
            long_running_store=long_store,
        )

        result = service.repair_job("longrun-persisted")

        self.assertTrue(result["success"])
        self.assertEqual(
            result["repair"]["status"],
            "AUTONOMOUS_REPAIR_QUEUED_WITH_ONE_TIME_APPROVAL",
        )


if __name__ == "__main__":
    unittest.main()

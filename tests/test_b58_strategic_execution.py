"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.long_running_autonomy_models import LongRunningJob
from app.ai.software_engineer.long_running_autonomy_store import LongRunningAutonomyStore
from app.ai.software_engineer.project_intelligence_models import ProjectOpportunity
from app.ai.software_engineer.project_intelligence_store import ProjectIntelligenceStore
from app.ai.software_engineer.self_directed_development_service import SelfDirectedDevelopmentService
from app.ai.software_engineer.self_directed_development_store import SelfDirectedDevelopmentStore
from app.ai.software_engineer.software_engineer_strategic_execution_formatter import (
    format_strategic_execution_response,
)
from app.ai.software_engineer.software_engineer_strategic_execution_router import (
    SoftwareEngineerStrategicExecutionRouter,
)
from app.ai.software_engineer.strategic_development_store import StrategicDevelopmentStore
from app.ai.software_engineer.strategic_execution_models import (
    StrategicExecutionPolicy,
    StrategicExecutionRecord,
)
from app.ai.software_engineer.strategic_execution_service import (
    StrategicExecutionService,
    bootstrap_strategic_execution,
)
from app.ai.software_engineer.strategic_execution_store import StrategicExecutionStore
from app.gui.command_safety import is_read_only_learning_command


def opportunity(
    opportunity_id: str = "opportunity-1111111111111111",
    *,
    status: str = "PENDING",
    job_id: str = "",
) -> dict:
    return ProjectOpportunity(
        opportunity_id=opportunity_id,
        title="Bezpieczny refaktor",
        objective="Bezpiecznie popraw moduł strategiczny.",
        target="app/ai/demo.py",
        fingerprint=f"fingerprint-{opportunity_id}",
        issue_type="LARGE_MODULE",
        value_score=80.0,
        risk_score=10.0,
        effort_score=5.0,
        confidence=0.9,
        final_score=75.0,
        status=status,
        job_id=job_id,
    ).to_dict()


class B58ModelsStoreTests(unittest.TestCase):

    def test_policy_never_auto_approves_and_limits_one_active(self) -> None:
        policy = StrategicExecutionPolicy.from_dict({
            "auto_approve": True,
            "max_active_executions": 99,
            "max_records": 999999,
        })
        self.assertFalse(policy.auto_approve)
        self.assertEqual(policy.max_active_executions, 1)
        self.assertEqual(policy.max_records, 10000)

    def test_record_normalizes_status_and_metadata(self) -> None:
        record = StrategicExecutionRecord.from_dict({
            "execution_id": " strategic-exec-one ",
            "goal_id": " strategic-one ",
            "opportunity_id": " opportunity-one ",
            "job_id": " longrun-one ",
            "status": "running",
            "metadata": {"safe": True},
        })
        self.assertEqual(record.status, "RUNNING")
        self.assertEqual(record.goal_id, "strategic-one")
        self.assertTrue(record.metadata["safe"])

    def test_store_persists_records_runtime_and_policy(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicExecutionStore(directory)
            store.save_record(StrategicExecutionRecord(
                execution_id="strategic-exec-one",
                goal_id="strategic-one",
                opportunity_id="opportunity-one",
                job_id="longrun-one",
            ))
            store.update_runtime({"phase": "WAITING_FOR_JOB"})
            store.update_policy({"auto_approve": True})
            restored = StrategicExecutionStore(directory)
            restored_runtime = restored.runtime()
            restored_policy = restored.policy()
            restored_summary = restored.summary()
        self.assertEqual(restored_runtime["phase"], "WAITING_FOR_JOB")
        self.assertFalse(restored_policy["auto_approve"])
        self.assertEqual(restored_summary["active"], 1)

    def test_store_finds_by_job_and_opportunity(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicExecutionStore(directory)
            store.save_record(StrategicExecutionRecord(
                execution_id="strategic-exec-one",
                goal_id="strategic-one",
                opportunity_id="opportunity-one",
                job_id="longrun-one",
            ))
            by_job = store.find_by_job("longrun-one")
            by_opportunity = store.find_by_opportunity("opportunity-one")
        self.assertEqual(by_job["execution_id"], "strategic-exec-one")
        self.assertEqual(by_opportunity["job_id"], "longrun-one")

    def test_store_history_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicExecutionStore(directory, max_history=100)
            store.update_policy({"max_history": 100})
            for index in range(140):
                store.record_history({
                    "status": f"EVENT-{index}",
                    "success": True,
                })
            history = store.history(limit=200)
        self.assertEqual(len(history), 100)
        self.assertEqual(history[0]["status"], "EVENT-139")


class B58ServiceTests(unittest.TestCase):

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.project_store = ProjectIntelligenceStore(self.root)
        self.long_store = LongRunningAutonomyStore(self.root)
        self.project = MagicMock()
        self.project.store = self.project_store
        self.project.long_running_service = SimpleNamespace(store=self.long_store)
        self.self_directed = MagicMock()
        self.strategic = MagicMock()
        self.strategic.store = StrategicDevelopmentStore(self.root)
        self.strategic.is_enabled.return_value = True
        self.strategic.refresh.return_value = {
            "success": True,
            "status": "STRATEGIC_DEVELOPMENT_ROADMAP_REFRESHED",
        }
        self.strategic.start_background.return_value = {
            "success": True,
            "status": "STRATEGIC_DEVELOPMENT_SUPERVISOR_STARTED",
        }
        self.strategic.pause.return_value = {"success": True}
        self.strategic.resume.return_value = {"success": True}
        self.strategic.recommend_opportunity.return_value = {
            "success": True,
            "status": "STRATEGIC_DEVELOPMENT_RECOMMENDATION_READY",
            "selected": {
                "goal_id": "strategic-one",
                "title": "Cel strategiczny",
                "subsystem": "app/ai",
                "issue_type": "LARGE_MODULE",
            },
            "recommendation": opportunity(),
        }
        self.project_store.save_opportunity(opportunity())
        self.store = StrategicExecutionStore(self.root)
        self.service = StrategicExecutionService(
            self.root,
            project_intelligence=self.project,
            self_directed=self.self_directed,
            strategic_development=self.strategic,
            store=self.store,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def configure_dispatch(self, job_id: str = "longrun-b58") -> None:
        def dispatch(opportunity_id: str, *, force: bool = False) -> dict:
            self.long_store.save_job(LongRunningJob(
                job_id=job_id,
                objective="Bezpiecznie popraw moduł strategiczny.",
                state="QUEUED",
            ))
            self.project_store.update_opportunity(opportunity_id, {
                "status": "DISPATCHED",
                "job_id": job_id,
            })
            return {
                "success": True,
                "status": "PROJECT_INTELLIGENCE_JOB_DISPATCHED",
                "job_id": job_id,
            }
        self.project.dispatch_opportunity.side_effect = dispatch

    def test_dispatch_binds_goal_opportunity_and_job(self) -> None:
        self.configure_dispatch()
        result = self.service.dispatch_next()
        record = self.store.find_by_job("longrun-b58")
        self.assertEqual(result["status"], "STRATEGIC_EXECUTION_JOB_DISPATCHED")
        self.assertEqual(record["goal_id"], "strategic-one")
        self.assertEqual(record["opportunity_id"], "opportunity-1111111111111111")
        self.project.dispatch_opportunity.assert_called_once_with(
            "opportunity-1111111111111111",
            force=True,
        )

    def test_dispatch_enriches_opportunity_and_long_job_metadata(self) -> None:
        self.configure_dispatch()
        self.service.dispatch_next()
        saved_opportunity = self.project_store.get_opportunity(
            "opportunity-1111111111111111"
        )
        saved_job = self.long_store.get_job("longrun-b58")
        self.assertEqual(
            saved_opportunity["metadata"]["strategic_goal_id"],
            "strategic-one",
        )
        self.assertEqual(
            saved_job["metadata"]["strategic_source"],
            "B58StrategicExecution",
        )
        self.assertTrue(saved_job["metadata"]["strategic_execution_id"])

    def test_active_limit_blocks_second_dispatch(self) -> None:
        self.configure_dispatch()
        first = self.service.dispatch_next()
        second = self.service.dispatch_next()
        self.assertEqual(first["status"], "STRATEGIC_EXECUTION_JOB_DISPATCHED")
        self.assertEqual(
            second["status"],
            "STRATEGIC_EXECUTION_WAITING_FOR_ACTIVE_JOB",
        )
        self.assertEqual(self.project.dispatch_opportunity.call_count, 1)

    def test_disabled_and_paused_do_not_dispatch(self) -> None:
        self.store.update_runtime({"enabled": False})
        disabled = self.service.dispatch_next()
        self.store.update_runtime({"enabled": True, "paused": True})
        paused = self.service.dispatch_next()
        self.assertEqual(disabled["status"], "STRATEGIC_EXECUTION_DISABLED")
        self.assertEqual(paused["status"], "STRATEGIC_EXECUTION_PAUSED")
        self.project.dispatch_opportunity.assert_not_called()

    def test_completed_outcome_updates_learning_counters(self) -> None:
        self.configure_dispatch()
        self.service.dispatch_next()
        item = self.project_store.update_opportunity(
            "opportunity-1111111111111111",
            {"status": "COMPLETED"},
        )
        result = self.service.observe_outcome(item, "COMPLETED")
        runtime = self.store.runtime()
        record = self.store.find_by_job("longrun-b58")
        self.assertEqual(result["outcome"], "COMPLETED")
        self.assertEqual(record["status"], "COMPLETED")
        self.assertEqual(runtime["completed_total"], 1)
        self.assertEqual(runtime["failed_total"], 0)

    def test_constraints_deferral_is_neutral_not_failure(self) -> None:
        self.configure_dispatch()
        self.service.dispatch_next()
        job = self.long_store.get_job("longrun-b58")
        job.update({
            "state": "CANCELLED",
            "last_result": {
                "status": "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS",
                "diagnostic_category": "CONSTRAINTS_PAUSE",
            },
        })
        self.long_store.save_job(job)
        item = self.project_store.update_opportunity(
            "opportunity-1111111111111111",
            {"status": "CANCELLED"},
        )
        self.service.observe_outcome(item, "DEFERRED_CONSTRAINTS")
        runtime = self.store.runtime()
        record = self.store.find_by_job("longrun-b58")
        self.assertEqual(record["status"], "DEFERRED_CONSTRAINTS")
        self.assertEqual(runtime["deferred_total"], 1)
        self.assertEqual(runtime["failed_total"], 0)

    def test_reconcile_detects_waiting_approval(self) -> None:
        self.configure_dispatch()
        self.service.dispatch_next()
        job = self.long_store.get_job("longrun-b58")
        job["state"] = "WAITING_APPROVAL"
        self.long_store.save_job(job)
        self.project_store.update_opportunity(
            "opportunity-1111111111111111",
            {"status": "WAITING_APPROVAL"},
        )
        result = self.service.reconcile(refresh_roadmap=False)
        record = self.store.find_by_job("longrun-b58")
        self.assertEqual(result["status"], "STRATEGIC_EXECUTION_RECONCILED")
        self.assertEqual(record["status"], "WAITING_APPROVAL")
        self.assertEqual(self.store.runtime()["phase"], "WAITING_APPROVAL")

    def test_reconcile_recovers_record_after_restart(self) -> None:
        job = LongRunningJob(
            job_id="longrun-recovered",
            objective="Odzyskane wykonanie.",
            state="RUNNING",
            metadata={
                "strategic_execution_id": "strategic-exec-recovered",
                "strategic_goal_id": "strategic-recovered",
                "strategic_opportunity_id": "opportunity-1111111111111111",
            },
        )
        self.long_store.save_job(job)
        result = self.service.reconcile(refresh_roadmap=False)
        record = self.store.get_record("strategic-exec-recovered")
        self.assertEqual(len(result["recovered"]), 1)
        self.assertEqual(record["status"], "RUNNING")
        self.assertTrue(record["metadata"]["recovered_after_restart"])

    def test_start_pause_resume_stop_keep_auto_approve_off(self) -> None:
        started = self.service.start()
        paused = self.service.pause()
        resumed = self.service.resume()
        stopped = self.service.stop()
        self.assertEqual(started["status"], "STRATEGIC_EXECUTION_STARTED")
        self.assertEqual(paused["status"], "STRATEGIC_EXECUTION_PAUSED")
        self.assertEqual(resumed["status"], "STRATEGIC_EXECUTION_RESUMED")
        self.assertEqual(stopped["status"], "STRATEGIC_EXECUTION_STOPPED")
        self.assertFalse(self.store.policy()["auto_approve"])
        self.strategic.start_background.assert_called_once_with()


class B58IntegrationTests(unittest.TestCase):

    def test_b56_dispatches_through_b58_bridge(self) -> None:
        with TemporaryDirectory() as directory:
            project = MagicMock()
            project.store = ProjectIntelligenceStore(directory)
            project.store.save_opportunity(opportunity())
            project.reconcile.return_value = {"success": True}
            project.scan_project.return_value = {"success": True}
            project.long_running_service = SimpleNamespace(
                store=LongRunningAutonomyStore(directory)
            )
            project.dispatch_opportunity.return_value = {
                "success": True,
                "status": "PROJECT_INTELLIGENCE_JOB_DISPATCHED",
                "job_id": "longrun-b58-bridge",
            }
            store = SelfDirectedDevelopmentStore(directory)
            store.update_policy({"auto_dispatch": True})
            store.update_runtime({"enabled": True, "paused": False})
            service = SelfDirectedDevelopmentService(
                directory,
                project_intelligence=project,
                store=store,
            )
            strategic = MagicMock()
            strategic.store = StrategicDevelopmentStore(directory)
            strategic.is_enabled.return_value = True
            strategic.recommend_opportunity.return_value = {
                "status": "STRATEGIC_DEVELOPMENT_RECOMMENDATION_READY",
                "selected": {"goal_id": "strategic-one"},
                "recommendation": opportunity(),
            }
            strategic.refresh.return_value = {"success": True}
            service.strategic_development_service = strategic
            result = service.run_cycle()
            bridge = service.strategic_execution_service
            bridge_summary = bridge.store.summary()
        self.assertEqual(result["status"], "SELF_DIRECTED_JOB_DISPATCHED")
        self.assertIsNotNone(bridge)
        self.assertEqual(bridge_summary["active"], 1)

    def test_bootstrap_attaches_b58_to_all_layers(self) -> None:
        with TemporaryDirectory() as directory:
            project = MagicMock()
            project.start_if_enabled.return_value = {}
            project.store = ProjectIntelligenceStore(directory)
            project.long_running_service = SimpleNamespace(
                store=LongRunningAutonomyStore(directory)
            )
            b56 = MagicMock()
            b56.start_if_enabled.return_value = {}
            b57 = MagicMock()
            b57.start_if_enabled.return_value = {}
            b57.is_enabled.return_value = False
            b57.store = StrategicDevelopmentStore(directory)
            controller = SimpleNamespace(
                project_root=directory,
                project_intelligence_service=project,
                self_directed_development_service=b56,
                strategic_development_service=b57,
            )
            service = bootstrap_strategic_execution(controller)
        self.assertIs(controller.strategic_execution_service, service)
        self.assertIs(project.strategic_execution_service, service)
        self.assertIs(b56.strategic_execution_service, service)
        self.assertIs(b57.strategic_execution_service, service)


class B58RoutingFormattingTests(unittest.TestCase):

    def test_router_routes_status_sync_and_start(self) -> None:
        service = MagicMock()
        service.status.return_value = {"status": "STRATEGIC_EXECUTION_STATUS"}
        service.reconcile.return_value = {
            "status": "STRATEGIC_EXECUTION_RECONCILED"
        }
        service.start.return_value = {"status": "STRATEGIC_EXECUTION_STARTED"}
        router = SoftwareEngineerStrategicExecutionRouter()
        controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split())
        )
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_execution_router."
            "bootstrap_strategic_execution",
            return_value=service,
        ):
            status = router.try_handle(
                controller,
                command="Pokaż status wykonania strategicznego",
                objective="",
                context={},
            )
            sync = router.try_handle(
                controller,
                command="Synchronizuj wykonanie strategiczne",
                objective="",
                context={},
            )
            start = router.try_handle(
                controller,
                command="Uruchom wykonanie strategiczne",
                objective="",
                context={},
            )
        self.assertEqual(status["status"], "STRATEGIC_EXECUTION_STATUS")
        self.assertEqual(sync["status"], "STRATEGIC_EXECUTION_RECONCILED")
        self.assertEqual(start["status"], "STRATEGIC_EXECUTION_STARTED")

    def test_formatter_reports_safety_and_execution_chain(self) -> None:
        text = format_strategic_execution_response({
            "status": "STRATEGIC_EXECUTION_STATUS",
            "runtime": {
                "enabled": True,
                "phase": "WAITING_FOR_JOB",
                "cycles_completed": 2,
                "active_goal_id": "strategic-one",
                "active_job_id": "longrun-one",
            },
            "policy": StrategicExecutionPolicy().to_dict(),
            "summary": {
                "total": 1,
                "active": 1,
                "completed": 0,
                "deferred": 0,
                "failed": 0,
                "waiting_approval": 0,
            },
            "roadmap_summary": {"total": 15, "pending": 13, "active": 1},
            "report_path": "data/autodev/strategic_execution.json",
        })
        self.assertIn("Wykonanie strategiczne B58", text)
        self.assertIn("Aktywny cel B57", text)
        self.assertIn("Aktywne zadanie B53/B54", text)
        self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_b58(self) -> None:
        text = BrainResponseFormatter()._format_software_engineer_response({
            "operation": "strategic_execution",
            "status": "STRATEGIC_EXECUTION_STATUS",
            "runtime": {},
            "policy": {},
            "summary": {},
        })
        self.assertIn("Wykonanie strategiczne B58", text)

    def test_status_is_read_only_but_start_and_sync_require_confirmation(self) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż status wykonania strategicznego"
            )
        )
        self.assertFalse(
            is_read_only_learning_command(
                "Uruchom wykonanie strategiczne"
            )
        )
        self.assertFalse(
            is_read_only_learning_command(
                "Synchronizuj wykonanie strategiczne"
            )
        )

    def test_controller_and_advanced_router_stay_below_audit_limits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        controller = root / "app/ai/software_engineer/autonomous_software_engineer.py"
        router = root / "app/ai/software_engineer/software_engineer_advanced_change_router.py"
        self.assertLess(len(controller.read_text(encoding="utf-8").splitlines()), 440)
        self.assertLess(len(router.read_text(encoding="utf-8").splitlines()), 360)

    def test_brain_bootstraps_b58_for_restart_recovery(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/ai/brain.py").read_text(encoding="utf-8")
        self.assertIn("bootstrap_strategic_execution", source)
        self.assertIn("self.strategic_execution_service", source)


if __name__ == "__main__":
    unittest.main()

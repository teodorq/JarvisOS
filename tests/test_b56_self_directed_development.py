from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.project_intelligence_models import (
    ProjectOpportunity,
)
from app.ai.software_engineer.project_intelligence_store import (
    ProjectIntelligenceStore,
)
from app.ai.software_engineer.self_directed_development_models import (
    SelfDirectedDevelopmentPolicy,
)
from app.ai.software_engineer.self_directed_development_service import (
    SelfDirectedDevelopmentService,
)
from app.ai.software_engineer.self_directed_development_store import (
    SelfDirectedDevelopmentStore,
)
from app.ai.software_engineer.software_engineer_self_directed_formatter import (
    format_self_directed_development_response,
)
from app.ai.software_engineer.software_engineer_self_directed_router import (
    SoftwareEngineerSelfDirectedRouter,
)
from app.gui.command_safety import is_read_only_learning_command


def opportunity(
    *,
    opportunity_id: str,
    fingerprint: str,
    status: str,
    job_id: str = "",
    error: str = "",
) -> dict:
    return ProjectOpportunity(
        opportunity_id=opportunity_id,
        title="Popraw moduł",
        objective="Bezpiecznie popraw app/demo.py.",
        target="app/demo.py",
        fingerprint=fingerprint,
        value_score=60,
        risk_score=10,
        effort_score=5,
        confidence=0.9,
        final_score=80,
        status=status,
        job_id=job_id,
        last_error=error,
    ).to_dict()


class B56ModelsStoreTests(unittest.TestCase):

    def test_policy_never_enables_auto_approve(self) -> None:
        policy = SelfDirectedDevelopmentPolicy.from_dict({
            "auto_approve": True,
            "interval_seconds": 1,
            "max_dispatches_per_day": 999,
        })
        self.assertFalse(policy.auto_approve)
        self.assertEqual(policy.interval_seconds, 30.0)
        self.assertEqual(policy.max_dispatches_per_day, 100)

    def test_policy_bounds_safety_limits(self) -> None:
        policy = SelfDirectedDevelopmentPolicy.from_dict({
            "max_consecutive_failures": 99,
            "max_active_jobs": 99,
            "cooldown_after_failure_seconds": 1,
        })
        self.assertEqual(policy.max_consecutive_failures, 10)
        self.assertEqual(policy.max_active_jobs, 3)
        self.assertEqual(policy.cooldown_after_failure_seconds, 30.0)

    def test_store_persists_runtime(self) -> None:
        with TemporaryDirectory() as directory:
            store = SelfDirectedDevelopmentStore(directory)
            store.update_runtime({"enabled": True, "phase": "SCANNING"})
            restored = SelfDirectedDevelopmentStore(directory).runtime()
        self.assertTrue(restored["enabled"])
        self.assertEqual(restored["phase"], "SCANNING")

    def test_store_policy_never_auto_approves(self) -> None:
        with TemporaryDirectory() as directory:
            store = SelfDirectedDevelopmentStore(directory)
            policy = store.update_policy({"auto_approve": True})
        self.assertFalse(policy["auto_approve"])

    def test_store_history_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            store = SelfDirectedDevelopmentStore(
                directory,
                max_history=50,
            )
            for index in range(70):
                store.record_history({
                    "status": f"CYCLE-{index}",
                    "success": True,
                })
            history = store.history(limit=100)
        self.assertEqual(len(history), 50)
        self.assertEqual(history[0]["status"], "CYCLE-69")

    def test_store_observed_jobs_are_persistent(self) -> None:
        with TemporaryDirectory() as directory:
            store = SelfDirectedDevelopmentStore(directory)
            store.mark_observed("longrun-1")
            restored = SelfDirectedDevelopmentStore(directory)
            self.assertTrue(restored.has_observed("longrun-1"))


class B56ServiceTests(unittest.TestCase):

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.project_store = ProjectIntelligenceStore(self.root)
        self.pi = MagicMock()
        self.pi.store = self.project_store
        self.pi.reconcile.return_value = {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_RECONCILED",
        }
        self.pi.scan_project.return_value = {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_SCAN_COMPLETED",
        }
        self.pi.select_best.return_value = {
            "success": True,
            "selected": {},
        }
        self.pi.dispatch_best.return_value = {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_JOB_DISPATCHED",
            "job_id": "longrun-b56",
        }
        self.pi.is_running.return_value = False
        self.pi.long_running_service = MagicMock()
        self.store = SelfDirectedDevelopmentStore(self.root)
        self.service = SelfDirectedDevelopmentService(
            self.root,
            project_intelligence=self.pi,
            store=self.store,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def enable(self) -> None:
        self.store.update_policy({"auto_dispatch": True})
        self.store.update_runtime({
            "enabled": True,
            "paused": False,
            "dispatch_day": datetime.now(timezone.utc).date().isoformat(),
        })

    def test_cycle_dispatches_best_when_safe(self) -> None:
        self.enable()
        result = self.service.run_cycle()
        self.assertEqual(result["status"], "SELF_DIRECTED_JOB_DISPATCHED")
        self.pi.dispatch_best.assert_called_once_with(force=True)
        runtime = self.store.runtime()
        self.assertEqual(runtime["last_dispatch_job_id"], "longrun-b56")
        self.assertEqual(runtime["dispatches_today"], 1)

    def test_cycle_never_passes_auto_approval(self) -> None:
        self.enable()
        self.service.run_cycle()
        self.assertFalse(self.store.policy()["auto_approve"])

    def test_cycle_waits_for_running_job(self) -> None:
        self.project_store.save_opportunity(opportunity(
            opportunity_id="opportunity-1111111111111111",
            fingerprint="running",
            status="RUNNING",
            job_id="longrun-running",
        ))
        self.enable()
        result = self.service.run_cycle()
        self.assertEqual(
            result["status"],
            "SELF_DIRECTED_WAITING_FOR_ACTIVE_JOB",
        )
        self.pi.scan_project.assert_not_called()
        self.pi.dispatch_best.assert_not_called()

    def test_cycle_stops_at_waiting_approval(self) -> None:
        self.project_store.save_opportunity(opportunity(
            opportunity_id="opportunity-2222222222222222",
            fingerprint="approval",
            status="WAITING_APPROVAL",
            job_id="longrun-approval",
        ))
        self.enable()
        result = self.service.run_cycle()
        self.assertEqual(result["status"], "SELF_DIRECTED_WAITING_APPROVAL")
        self.assertEqual(
            self.store.runtime()["waiting_approval_job_id"],
            "longrun-approval",
        )
        self.pi.dispatch_best.assert_not_called()

    def test_completed_outcome_resets_failure_counter(self) -> None:
        self.project_store.save_opportunity(opportunity(
            opportunity_id="opportunity-3333333333333333",
            fingerprint="completed",
            status="COMPLETED",
            job_id="longrun-completed",
        ))
        self.store.update_runtime({"consecutive_failures": 2})
        result = self.service.run_cycle()
        self.assertTrue(result["success"])
        runtime = self.store.runtime()
        self.assertEqual(runtime["consecutive_failures"], 0)
        self.assertEqual(runtime["completed_total"], 1)
        self.assertTrue(self.store.has_observed("longrun-completed"))

    def test_failed_outcome_starts_cooldown(self) -> None:
        self.project_store.save_opportunity(opportunity(
            opportunity_id="opportunity-4444444444444444",
            fingerprint="failed",
            status="FAILED",
            job_id="longrun-failed",
            error="tests failed",
        ))
        result = self.service.run_cycle()
        self.assertIn(
            result["status"],
            {"SELF_DIRECTED_COOLDOWN", "SELF_DIRECTED_CYCLE_OBSERVE_ONLY"},
        )
        runtime = self.store.runtime()
        self.assertEqual(runtime["consecutive_failures"], 1)
        self.assertEqual(runtime["failed_total"], 1)
        self.assertTrue(runtime["cooldown_until"])

    def test_terminal_outcome_is_observed_once(self) -> None:
        self.project_store.save_opportunity(opportunity(
            opportunity_id="opportunity-5555555555555555",
            fingerprint="once",
            status="FAILED",
            job_id="longrun-once",
        ))
        self.service.run_cycle()
        first = self.store.runtime()["failed_total"]
        self.service.run_cycle()
        second = self.store.runtime()["failed_total"]
        self.assertEqual(first, second)

    def test_circuit_breaker_pauses_after_limit(self) -> None:
        self.store.update_runtime({"consecutive_failures": 3})
        result = self.service.run_cycle()
        self.assertEqual(result["status"], "SELF_DIRECTED_CIRCUIT_OPEN")
        self.assertTrue(self.store.runtime()["paused"])

    def test_daily_budget_blocks_dispatch(self) -> None:
        self.enable()
        self.store.update_policy({"max_dispatches_per_day": 2})
        self.store.update_runtime({"dispatches_today": 2})
        result = self.service.run_cycle()
        self.assertEqual(
            result["status"],
            "SELF_DIRECTED_DAILY_BUDGET_EXHAUSTED",
        )
        self.pi.dispatch_best.assert_not_called()

    def test_force_cycle_can_dispatch_while_supervisor_disabled(self) -> None:
        result = self.service.run_cycle(force_dispatch=True)
        self.assertEqual(result["status"], "SELF_DIRECTED_JOB_DISPATCHED")

    def test_no_candidate_does_not_consume_budget(self) -> None:
        self.enable()
        self.pi.dispatch_best.return_value = {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_NO_SAFE_CANDIDATE",
            "job_id": "",
        }
        result = self.service.run_cycle()
        self.assertEqual(result["status"], "SELF_DIRECTED_NO_SAFE_CANDIDATE")
        self.assertEqual(self.store.runtime()["dispatches_today"], 0)

    def test_start_starts_long_running_and_disables_b55_loop(self) -> None:
        self.pi.is_running.return_value = True
        thread = MagicMock()
        thread.is_alive.return_value = False
        with patch(
            "app.ai.software_engineer.self_directed_development_service.threading.Thread",
            return_value=thread,
        ):
            result = self.service.start_background()
        self.assertEqual(result["status"], "SELF_DIRECTED_SUPERVISOR_STARTED")
        self.pi.stop_background.assert_called_once_with()
        self.pi.long_running_service.start_background.assert_called_once_with()
        thread.start.assert_called_once_with()
        self.assertTrue(self.store.runtime()["enabled"])
        self.assertFalse(self.store.policy()["auto_approve"])

    def test_stop_disables_auto_dispatch(self) -> None:
        self.store.update_policy({"auto_dispatch": True})
        result = self.service.stop_background()
        self.assertEqual(result["status"], "SELF_DIRECTED_SUPERVISOR_STOPPED")
        self.assertFalse(self.store.policy()["auto_dispatch"])

    def test_resume_resets_circuit_breaker(self) -> None:
        self.store.update_runtime({
            "paused": True,
            "consecutive_failures": 3,
            "cooldown_until": "2099-01-01T00:00:00+00:00",
        })
        result = self.service.resume()
        self.assertEqual(result["status"], "SELF_DIRECTED_SUPERVISOR_RESUMED")
        runtime = self.store.runtime()
        self.assertFalse(runtime["paused"])
        self.assertEqual(runtime["consecutive_failures"], 0)
        self.assertEqual(runtime["cooldown_until"], "")

    def test_status_includes_project_summary(self) -> None:
        result = self.service.status()
        self.assertIn("project_summary", result)
        self.assertEqual(result["operation"], "self_directed_development")


class B56RoutingFormattingTests(unittest.TestCase):

    def test_controller_recognizes_start_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Uruchom samodzielny rozwój JARVIS-a"
            )
        )

    def test_status_command_is_read_only(self) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż status samodzielnego rozwoju"
            )
        )

    def test_start_command_requires_confirmation(self) -> None:
        self.assertFalse(
            is_read_only_learning_command(
                "Uruchom samodzielny rozwój JARVIS-a"
            )
        )

    def test_router_routes_status(self) -> None:
        service = MagicMock()
        service.start_if_enabled.return_value = {}
        service.status.return_value = {
            "success": True,
            "status": "SELF_DIRECTED_DEVELOPMENT_STATUS",
        }
        controller = SimpleNamespace(
            project_root=Path.cwd(),
            self_directed_development_service=service,
            _normalize=AutonomousSoftwareEngineerController._normalize,
        )
        result = SoftwareEngineerSelfDirectedRouter().try_handle(
            controller,
            command="Pokaż status samodzielnego rozwoju",
            objective="",
            context={},
        )
        self.assertEqual(result["status"], "SELF_DIRECTED_DEVELOPMENT_STATUS")
        service.status.assert_called_once_with()

    def test_router_routes_start(self) -> None:
        service = MagicMock()
        service.start_if_enabled.return_value = {}
        service.start_background.return_value = {
            "success": True,
            "status": "SELF_DIRECTED_SUPERVISOR_STARTED",
        }
        controller = SimpleNamespace(
            project_root=Path.cwd(),
            self_directed_development_service=service,
            _normalize=AutonomousSoftwareEngineerController._normalize,
        )
        result = SoftwareEngineerSelfDirectedRouter().try_handle(
            controller,
            command="Uruchom samodzielny rozwój JARVIS-a",
            objective="",
            context={},
        )
        self.assertEqual(result["status"], "SELF_DIRECTED_SUPERVISOR_STARTED")

    def test_formatter_reports_safety_and_phase(self) -> None:
        text = format_self_directed_development_response({
            "status": "SELF_DIRECTED_DEVELOPMENT_STATUS",
            "runtime": {
                "enabled": True,
                "phase": "WAITING_APPROVAL",
                "cycles_completed": 5,
                "dispatches_today": 1,
            },
            "policy": {
                "max_dispatches_per_day": 10,
                "auto_dispatch": True,
                "auto_approve": False,
            },
            "project_summary": {"total": 10, "pending": 9, "active": 1},
        })
        self.assertIn("Faza: WAITING_APPROVAL", text)
        self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_b56_operation(self) -> None:
        text = BrainResponseFormatter()._format_software_engineer_response({
            "success": True,
            "status": "SELF_DIRECTED_DEVELOPMENT_STATUS",
            "operation": "self_directed_development",
            "runtime": {},
            "policy": {},
            "project_summary": {},
        })
        self.assertIn("Samodzielny rozwój B56", text)

    def test_advanced_router_remains_below_audit_limit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        router = (
            root
            / "app"
            / "ai"
            / "software_engineer"
            / "software_engineer_advanced_change_router.py"
        )
        self.assertLess(len(router.read_text(encoding="utf-8").splitlines()), 360)


if __name__ == "__main__":
    unittest.main()

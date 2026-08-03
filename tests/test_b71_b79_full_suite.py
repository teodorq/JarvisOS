"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import time
import unittest
from unittest.mock import MagicMock, patch

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_release_train_service import (
    AutonomousReleaseTrainService,
)
from app.ai.software_engineer.autonomy_governance_models import (
    harden_stage_policy,
)
from app.ai.software_engineer.autonomy_governance_store import (
    AutonomyGovernanceStore,
)
from app.ai.software_engineer.global_autonomy_watchdog_service import (
    GlobalAutonomyWatchdogService,
)
from app.ai.software_engineer.long_term_development_memory_service import (
    LongTermDevelopmentMemoryService,
)
from app.ai.software_engineer.production_autonomy_24x7_service import (
    ProductionAutonomy24x7Service,
)
from app.ai.software_engineer.recovery_execution_controller_service import (
    RecoveryExecutionControllerService,
)
from app.ai.software_engineer.recovery_learning_service import (
    RecoveryLearningService,
)
from app.ai.software_engineer.safe_autonomous_deployment_service import (
    SafeAutonomousDeploymentService,
)
from app.ai.software_engineer.security_hardening_service import (
    SecurityHardeningService,
)
from app.ai.software_engineer.software_engineer_autonomy_governance_formatter import (
    format_autonomy_governance_response,
)
from app.ai.software_engineer.software_engineer_autonomy_governance_router import (
    SoftwareEngineerAutonomyGovernanceRouter,
)
from app.ai.software_engineer.software_engineer_autonomy_operations_router import (
    SoftwareEngineerAutonomyOperationsRouter,
)
from app.ai.software_engineer.unified_autonomy_control_center_service import (
    UnifiedAutonomyControlCenterService,
)
from app.gui.command_safety import is_read_only_learning_command


class FakeRecovery:
    def __init__(self, store: AutonomyGovernanceStore) -> None:
        self.store = store
        self.plan_latest = MagicMock(side_effect=self._plan)
        self.execute_latest = MagicMock(side_effect=self._execute)
        self.verify_latest = MagicMock(return_value={
            "success": True,
            "status": "AUTONOMOUS_RECOVERY_VERIFIED",
            "plan": {"status": "COMPLETED"},
            "errors": [],
        })

    def _plan(self):
        plan = self.store.append_record("B70", {
            "recovery_id": "recovery-1",
            "incident_id": "incident-1",
            "category": "ORPHANED_B68_LEASE",
            "status": "PREVIEW_READY",
            "steps": ["STOP_B68", "RELEASE_B68_LEASES"],
        })
        return {
            "success": True,
            "status": "AUTONOMOUS_RECOVERY_PLAN_READY",
            "plan": plan,
        }

    def _execute(self):
        values = list(reversed(self.store.list_records("B70", limit=100)))
        plan = values[-1] if values else {}
        for item in values:
            if str(item.get("recovery_id", "")) == "recovery-1":
                item["status"] = "COMPLETED"
                plan = item
        self.store.replace_records("B70", values)
        return {
            "success": True,
            "status": "AUTONOMOUS_RECOVERY_COMPLETED",
            "plan": plan,
            "errors": [],
        }


class FakeReleaseManager:
    def __init__(self) -> None:
        self.create_candidate = MagicMock(return_value={
            "success": True,
            "status": "AUTONOMOUS_RELEASE_CANDIDATE_READY",
            "release": {
                "release_id": "release-1",
                "snapshot_path": "archive/release-1.zip",
                "manifest_hash": "abc",
            },
        })
        self.activate = MagicMock(return_value={
            "success": True,
            "status": "AUTONOMOUS_RELEASE_ACTIVATED",
            "errors": [],
        })
        self.restore_previous = MagicMock(return_value={
            "success": True,
            "status": "AUTONOMOUS_RELEASE_ROLLED_BACK",
            "errors": [],
        })


class FakeSupervisor:
    def __init__(self, status: str = "OK") -> None:
        self.status_name = status
        self.alive = False
        self.start_background = MagicMock(side_effect=self._start)
        self.stop_background = MagicMock(side_effect=self._stop)
        self.pause = MagicMock(return_value={"success": True, "status": "PAUSED"})
        self.resume = MagicMock(return_value={"success": True, "status": "RESUMED"})

    def _start(self):
        self.alive = True
        return {"success": True, "status": "STARTED"}

    def _stop(self):
        self.alive = False
        return {"success": True, "status": "STOPPED"}

    def is_running(self) -> bool:
        return self.alive


class FakeCycleService:
    def __init__(self, method: str) -> None:
        setattr(self, method, MagicMock(return_value={
            "success": True,
            "status": f"{method.upper()}_OK",
        }))


class B71B79FullSuiteTests(unittest.TestCase):
    def test_policies_are_bounded_and_never_auto_approve(self):
        cases = {
            "B71": {"require_manual_execution": False, "auto_approve": True},
            "B72": {"interval_seconds": 1, "auto_approve": True},
            "B73": {"safe_supervisors_only": False, "auto_approve": True},
            "B74": {"auto_restart_safe": True, "auto_approve": True},
            "B75": {"auto_promote": True, "auto_approve": True},
            "B76": {"require_manual_stable_mark": False, "auto_approve": True},
            "B77": {"max_memories": 999999, "auto_approve": True},
            "B78": {"safe_hardening_only": False, "auto_approve": True},
            "B79": {
                "automatic_code_execution": True,
                "resume_after_restart": True,
                "auto_approve": True,
            },
        }
        for stage, source in cases.items():
            policy = harden_stage_policy(stage, source)
            self.assertFalse(policy["auto_approve"], stage)
        self.assertTrue(harden_stage_policy("B71", cases["B71"])["require_manual_execution"])
        self.assertFalse(harden_stage_policy("B74", cases["B74"])["auto_restart_safe"])
        self.assertFalse(harden_stage_policy("B75", cases["B75"])["auto_promote"])
        self.assertTrue(harden_stage_policy("B76", cases["B76"])["require_manual_stable_mark"])
        self.assertFalse(harden_stage_policy("B79", cases["B79"])["automatic_code_execution"])
        self.assertTrue(harden_stage_policy("B79", cases["B79"])["resume_after_restart"])

    def test_store_persists_all_b71_b79_sections(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            for value, stage in enumerate(range(71, 80), 1):
                key = f"B{stage}"
                item = store.append_record(key, {
                    "status": "ACTIVE",
                    f"id_{stage}": value,
                })
                self.assertEqual(item["stage"], key)
                self.assertEqual(len(store.list_records(key)), 1)
            compact = store.compact()
            for stage in range(71, 80):
                self.assertIn(f"B{stage}", compact)

    def test_b71_executes_only_ready_plan_and_records_result(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            recovery = FakeRecovery(store)
            recovery._plan()
            service = RecoveryExecutionControllerService(
                directory,
                store=store,
                recovery_orchestrator=recovery,
            )
            result = service.execute_latest()
            self.assertTrue(result["success"])
            self.assertEqual(result["execution"]["status"], "COMPLETED")
            self.assertTrue(result["execution"]["requires_confirmation"])
            self.assertFalse(result["execution"]["auto_approve"])
            recovery.execute_latest.assert_called_once()

    def test_b71_respects_b72_block(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            recovery = FakeRecovery(store)
            recovery._plan()
            learning = SimpleNamespace(
                allow_execution=lambda plan: {
                    "allowed": False,
                    "reason": "blocked",
                }
            )
            service = RecoveryExecutionControllerService(
                directory,
                store=store,
                recovery_orchestrator=recovery,
                recovery_learning=learning,
            )
            result = service.execute_latest()
            self.assertFalse(result["success"])
            self.assertEqual(
                result["status"],
                "RECOVERY_EXECUTION_BLOCKED_BY_LEARNING",
            )
            recovery.execute_latest.assert_not_called()

    def test_b72_ranks_and_blocks_ineffective_runbook(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            for index in range(3):
                store.append_record("B71", {
                    "execution_id": f"e{index}",
                    "category": "TEST_FAILURE",
                    "runbook": ["A", "B"],
                    "status": "FAILED",
                })
            service = RecoveryLearningService(directory, store=store)
            result = service.run_cycle()
            self.assertEqual(result["blocked_categories"], 1)
            gate = service.allow_execution({"category": "TEST_FAILURE"})
            self.assertFalse(gate["allowed"])

    def test_b73_aggregates_and_controls_safe_supervisors(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            services = {
                "B69": FakeSupervisor(),
                "B70": FakeSupervisor(),
                "B72": FakeSupervisor(),
                "B74": FakeSupervisor(),
            }
            center = UnifiedAutonomyControlCenterService(
                directory,
                store=store,
                services=services,
            )
            status = center.status()
            self.assertEqual(status["suite_span"], "B56-B79")
            self.assertIn("B79", status["stage_summaries"])
            started = center.start_safe_supervisors()
            self.assertTrue(started["success"])
            stopped = center.stop_all_supervisors()
            self.assertTrue(stopped["success"])

    def test_b74_reconciles_missing_worker(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            store.update_runtime("B69", {
                "running": True,
                "phase": "MONITORING",
            })
            service = FakeSupervisor()
            watchdog = GlobalAutonomyWatchdogService(
                directory,
                store=store,
                services={"B69": service},
            )
            result = watchdog.run_cycle()
            self.assertEqual(result["status"], "GLOBAL_WATCHDOG_EVENTS")
            self.assertFalse(store.runtime("B69")["running"])
            self.assertEqual(
                store.runtime("B69")["phase"],
                "RECOVERED_AFTER_WATCHDOG",
            )

    def test_b75_candidate_canary_promotion_and_rollback(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            release = FakeReleaseManager()
            service = SafeAutonomousDeploymentService(
                directory,
                store=store,
                release_manager=release,
            )
            candidate = service.create_candidate()
            self.assertEqual(candidate["deployment"]["status"], "PREVIEW_READY")
            canary = service.start_canary()
            self.assertEqual(canary["deployment"]["status"], "CANARY")
            promoted = service.promote_latest()
            self.assertEqual(promoted["deployment"]["status"], "PROMOTED")
            rolled_back = service.rollback_latest()
            self.assertEqual(rolled_back["deployment"]["status"], "ROLLED_BACK")
            release.activate.assert_called_once()
            release.restore_previous.assert_called_once()

    def test_b76_builds_changelog_and_marks_stable(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            store.append_record("B75", {
                "deployment_id": "d1",
                "release_id": "r1",
                "manifest_hash": "abc",
                "snapshot_path": "snapshot.zip",
                "status": "PROMOTED",
            })
            store.record_history("B75", {
                "status": "SAFE_DEPLOYMENT_PROMOTED",
                "success": True,
                "phase": "PROMOTED",
                "decision": "PROMOTE",
            })
            service = AutonomousReleaseTrainService(directory, store=store)
            ready = service.create_release_train()
            self.assertEqual(
                ready["release_train"]["status"],
                "READY_FOR_STABLE_MARK",
            )
            stable = service.mark_stable()
            self.assertEqual(stable["release_train"]["status"], "STABLE")
            self.assertTrue(stable["release_train"]["changelog"])

    def test_b77_deduplicates_long_term_memories(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            store.record_history("B71", {
                "status": "RECOVERY_EXECUTION_COMPLETED",
                "success": True,
                "phase": "COMPLETED",
                "decision": "RECOVERED",
            })
            service = LongTermDevelopmentMemoryService(directory, store=store)
            first = service.capture()
            second = service.capture()
            self.assertGreaterEqual(first["created_count"], 1)
            self.assertEqual(second["created_count"], 0)

    def test_b78_audit_and_safe_hardening(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app" / "unsafe.py").write_text(
                "import subprocess\nsubprocess.run('x', shell=True)\n",
                encoding="utf-8",
            )
            store = AutonomyGovernanceStore(directory)
            service = SecurityHardeningService(directory, store=store)
            result = service.audit()
            categories = {
                item["category"] for item in result["findings"]
            }
            self.assertIn("SHELL_TRUE", categories)
            hardened = service.apply_safe_hardening()
            self.assertTrue(hardened["success"])
            for stage in range(62, 80):
                self.assertFalse(store.policy(f"B{stage}")["auto_approve"])
            self.assertEqual(store.policy("B64")["max_active_leases"], 1)

    def test_b79_runs_monitoring_steps_without_code_execution(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            services = {
                "B69": FakeCycleService("scan"),
                "B70": FakeCycleService("run_cycle"),
                "B72": FakeCycleService("run_cycle"),
                "B74": FakeCycleService("run_cycle"),
                "B77": FakeCycleService("capture"),
            }
            service = ProductionAutonomy24x7Service(
                directory,
                store=store,
                services=services,
            )
            result = service.run_cycle()
            self.assertTrue(result["success"])
            self.assertEqual(result["cycle"]["status"], "COMPLETED")
            self.assertFalse(result["cycle"]["auto_approve"])
            self.assertFalse(
                service.status()["safety"]["automatic_code_execution"]
            )

    def test_b79_start_stop_and_restart_reconciliation(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            service = ProductionAutonomy24x7Service(
                directory,
                store=store,
                services={},
            )
            with patch.object(
                service,
                "run_cycle",
                return_value={"success": True},
            ):
                started = service.start_background()
                self.assertTrue(started["success"])
                time.sleep(0.03)
                stopped = service.stop_background()
            self.assertIn(
                stopped["runtime"]["phase"],
                {"STOPPED", "STOPPED_PENDING_WORKER"},
            )
            self.assertFalse(store.policy("B79")["auto_approve"])

            store.update_runtime("B79", {
                "running": True,
                "phase": "MONITORING",
            })
            ProductionAutonomy24x7Service(
                directory,
                store=store,
                services={},
            )
            self.assertFalse(store.runtime("B79")["running"])
            self.assertEqual(
                store.runtime("B79")["phase"],
                "RECOVERED_AFTER_RESTART",
            )

    def test_router_controller_safety_and_formatter_cover_b71_b79(self):
        router = SoftwareEngineerAutonomyGovernanceRouter()
        operations = SoftwareEngineerAutonomyOperationsRouter()
        status_commands = (
            "Pokaż status wykonania odzyskiwania",
            "Pokaż status uczenia napraw",
            "Pokaż centrum sterowania autonomią",
            "Pokaż status globalnego watchdoga",
            "Pokaż status bezpiecznego wdrożenia",
            "Pokaż status menedżera wydań",
            "Pokaż status pamięci rozwoju",
            "Pokaż status bezpieczeństwa autonomii",
            "Pokaż status produkcyjnej autonomii",
        )
        for command in status_commands:
            self.assertTrue(router.can_handle(command), command)
            self.assertTrue(operations.can_handle(command), command)
            self.assertTrue(is_read_only_learning_command(command), command)
        mutating = (
            "Wykonaj zatwierdzony plan odzyskiwania",
            "Przeprowadź cykl uczenia napraw",
            "Uruchom globalny watchdog",
            "Promuj bezpieczne wdrożenie",
            "Oznacz wydanie jako stabilne",
            "Zapisz pamięć rozwoju",
            "Zastosuj bezpieczne utwardzenie",
            "Uruchom produkcyjną autonomię 24/7",
        )
        for command in mutating:
            self.assertTrue(router.can_handle(command), command)
            self.assertFalse(is_read_only_learning_command(command), command)

        for stage in range(71, 80):
            text = format_autonomy_governance_response({
                "status": "STATUS",
                "stage": f"B{stage}",
                "runtime": {"phase": "READY", "cycles_completed": 1},
                "policy": {"auto_approve": False},
                "summary": {},
            })
            self.assertIn(f"B{stage}", text)
            self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_b79(self):
        text = BrainResponseFormatter()._format_software_engineer_response({
            "operation": "autonomy_governance_suite",
            "stage": "B79",
            "status": "PRODUCTION_AUTONOMY_24X7_STATUS",
            "runtime": {},
            "policy": {},
            "summary": {},
            "cycles": [],
        })
        self.assertIn("B79", text)

    def test_source_limits_remain_bounded(self):
        project = Path(__file__).resolve().parents[1]
        limits = {
            "app/ai/software_engineer/autonomy_governance_store.py": 440,
            "app/ai/software_engineer/software_engineer_autonomy_governance_router.py": 440,
            "app/ai/software_engineer/software_engineer_autonomy_operations_router.py": 440,
            "app/ai/software_engineer/autonomous_software_engineer.py": 440,
            "app/ai/software_engineer/autonomy_stage_utils.py": 320,
            "app/ai/software_engineer/recovery_execution_controller_service.py": 420,
            "app/ai/software_engineer/recovery_learning_service.py": 320,
            "app/ai/software_engineer/unified_autonomy_control_center_service.py": 320,
            "app/ai/software_engineer/global_autonomy_watchdog_service.py": 320,
            "app/ai/software_engineer/safe_autonomous_deployment_service.py": 420,
            "app/ai/software_engineer/autonomous_release_train_service.py": 320,
            "app/ai/software_engineer/long_term_development_memory_service.py": 320,
            "app/ai/software_engineer/security_hardening_service.py": 360,
            "app/ai/software_engineer/production_autonomy_24x7_service.py": 320,
        }
        for relative, limit in limits.items():
            lines = (project / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, relative)


if __name__ == "__main__":
    unittest.main()

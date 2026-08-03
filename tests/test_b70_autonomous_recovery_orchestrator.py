from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import time
import unittest
from unittest.mock import MagicMock, patch

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_recovery_orchestrator_service import (
    AutonomousRecoveryOrchestratorService,
)
from app.ai.software_engineer.autonomy_governance_models import (
    harden_stage_policy,
)
from app.ai.software_engineer.autonomy_governance_store import (
    AutonomyGovernanceStore,
)
from app.ai.software_engineer.autonomy_governance_suite import (
    AutonomyGovernanceSuite,
)
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_autonomy_governance_formatter import (
    format_autonomy_governance_response,
)
from app.ai.software_engineer.software_engineer_autonomy_governance_router import (
    SoftwareEngineerAutonomyGovernanceRouter,
)
from app.gui.command_safety import is_read_only_learning_command


class FakeFullAutonomy:
    def __init__(self, store: AutonomyGovernanceStore) -> None:
        self.store = store
        self.stop_background = MagicMock(side_effect=self._stop)

    def _stop(self):
        self.store.update_policy("B68", {
            "enabled": False,
            "auto_approve": False,
        })
        self.store.update_runtime("B68", {
            "enabled": False,
            "running": False,
            "phase": "STOPPED",
            "last_error": "",
        })
        return {
            "success": True,
            "status": "FULL_24X7_AUTONOMY_STOPPED",
        }

    def is_running(self) -> bool:
        return False


class FakeBudget:
    def __init__(self, store: AutonomyGovernanceStore) -> None:
        self.store = store
        self.release_owner_leases = MagicMock(side_effect=self._release)

    def _release(self, owner, *, success, reason):
        self.store.update_runtime("B64", {
            "phase": "READY",
            "active_leases": 0,
            "last_error": "",
        })
        return {
            "success": True,
            "status": "RESOURCE_BUDGET_OWNER_LEASES_RELEASED",
            "released_count": 1,
            "owner": owner,
            "reason": reason,
        }


class FakeIncidentResponse:
    def __init__(
        self,
        store: AutonomyGovernanceStore,
        *,
        resolve_on_scan: bool = True,
    ) -> None:
        self.store = store
        self.resolve_on_scan = resolve_on_scan
        self.scan = MagicMock(side_effect=self._scan)

    def _scan(self):
        if self.resolve_on_scan:
            records = list(reversed(self.store.list_records("B69", limit=1000)))
            for item in records:
                if str(item.get("status", "")).upper() in {"OPEN", "CONTAINED"}:
                    item["status"] = "RESOLVED"
                    item["resolution"] = "TEST_RECOVERED"
            self.store.replace_records("B69", records)
        return {
            "success": True,
            "status": "AUTONOMOUS_INCIDENT_SCAN_COMPLETED",
            "detected": 0,
        }


class B70AutonomousRecoveryOrchestratorTests(unittest.TestCase):
    def _service(
        self,
        directory: str,
        *,
        resolve_on_scan: bool = True,
    ):
        store = AutonomyGovernanceStore(directory)
        budget = FakeBudget(store)
        full = FakeFullAutonomy(store)
        incidents = FakeIncidentResponse(
            store,
            resolve_on_scan=resolve_on_scan,
        )
        service = AutonomousRecoveryOrchestratorService(
            directory,
            store=store,
            incident_response=incidents,
            resource_budget=budget,
            full_autonomy=full,
        )
        return service, store, incidents, budget, full

    @staticmethod
    def _incident(
        store: AutonomyGovernanceStore,
        *,
        category: str = "ORPHANED_B68_LEASE",
        status: str = "OPEN",
        severity: str = "CRITICAL",
    ) -> dict:
        return store.append_record("B69", {
            "incident_id": f"incident-{category}",
            "fingerprint": f"fp-{category}",
            "status": status,
            "category": category,
            "stage_name": "B64" if "LEASE" in category else "B68",
            "severity": severity,
            "summary": "test",
        })

    def test_policy_is_bounded_and_never_executes_automatically(self):
        policy = harden_stage_policy("B70", {
            "enabled": True,
            "interval_seconds": 1,
            "max_plans": 999999,
            "max_attempts_per_incident": 999,
            "auto_execute_safe": True,
            "require_manual_execution": False,
            "auto_approve": True,
        })
        self.assertEqual(policy["interval_seconds"], 30.0)
        self.assertEqual(policy["max_plans"], 10000)
        self.assertEqual(policy["max_attempts_per_incident"], 10)
        self.assertFalse(policy["auto_execute_safe"])
        self.assertTrue(policy["require_manual_execution"])
        self.assertFalse(policy["auto_approve"])

    def test_store_persists_recovery_plans(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            item = store.append_record("B70", {
                "recovery_id": "r1",
                "status": "PREVIEW_READY",
            })
            self.assertEqual(item["stage"], "B70")
            self.assertEqual(store.list_records("B70")[0]["recovery_id"], "r1")
            self.assertIn("B70", store.compact())

    def test_plan_latest_holds_without_incident(self):
        with TemporaryDirectory() as directory:
            service, _, _, _, _ = self._service(directory)
            result = service.plan_latest()
            self.assertEqual(result["status"], "AUTONOMOUS_RECOVERY_NO_INCIDENT")
            self.assertEqual(result["decision"], "HOLD")

    def test_orphaned_lease_builds_bounded_preview(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(directory)
            self._incident(store)
            result = service.plan_latest()
            plan = result["plan"]
            self.assertEqual(plan["status"], "PREVIEW_READY")
            self.assertIn("RELEASE_B68_LEASES", plan["steps"])
            self.assertTrue(plan["requires_confirmation"])
            self.assertFalse(plan["auto_approve"])

    def test_repeated_planning_reuses_active_plan(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(directory)
            self._incident(store)
            first = service.plan_latest()["plan"]
            second = service.plan_latest()["plan"]
            self.assertEqual(first["recovery_id"], second["recovery_id"])
            self.assertEqual(len(store.list_records("B70", limit=10)), 1)

    def test_unknown_incident_is_blocked(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(directory)
            self._incident(
                store,
                category="STAGE_FAILURE_THRESHOLD",
                severity="HIGH",
            )
            result = service.plan_latest()
            self.assertEqual(result["status"], "AUTONOMOUS_RECOVERY_PLAN_BLOCKED")
            self.assertEqual(result["plan"]["status"], "BLOCKED")
            self.assertEqual(result["decision"], "HOLD")

    def test_execute_safe_plan_stops_b68_releases_lease_and_verifies(self):
        with TemporaryDirectory() as directory:
            service, store, incidents, budget, full = self._service(directory)
            self._incident(store)
            store.update_runtime("B64", {
                "phase": "LEASED",
                "active_leases": 1,
            })
            store.update_runtime("B68", {
                "running": True,
                "phase": "RUNNING",
            })
            service.plan_latest()
            result = service.execute_latest()
            self.assertEqual(result["status"], "AUTONOMOUS_RECOVERY_COMPLETED")
            self.assertEqual(result["plan"]["status"], "COMPLETED")
            self.assertEqual(store.runtime("B64")["active_leases"], 0)
            self.assertEqual(store.runtime("B64")["phase"], "READY")
            self.assertEqual(store.runtime("B68")["phase"], "STOPPED")
            full.stop_background.assert_called_once()
            budget.release_owner_leases.assert_called_once()
            incidents.scan.assert_called()

    def test_execute_blocked_plan_does_not_mutate_runtime(self):
        with TemporaryDirectory() as directory:
            service, store, incidents, budget, full = self._service(directory)
            self._incident(store, category="STAGE_FAILURE_THRESHOLD")
            service.plan_latest()
            result = service.execute_latest()
            self.assertEqual(result["status"], "AUTONOMOUS_RECOVERY_EXECUTION_BLOCKED")
            full.stop_background.assert_not_called()
            budget.release_owner_leases.assert_not_called()
            incidents.scan.assert_not_called()

    def test_verification_failure_is_persisted(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(
                directory,
                resolve_on_scan=False,
            )
            self._incident(store)
            store.update_runtime("B64", {
                "phase": "LEASED",
                "active_leases": 1,
            })
            store.update_runtime("B68", {
                "running": True,
                "phase": "RUNNING",
            })
            service.plan_latest()
            result = service.execute_latest()
            self.assertEqual(
                result["status"],
                "AUTONOMOUS_RECOVERY_VERIFICATION_FAILED",
            )
            self.assertEqual(result["plan"]["status"], "VERIFICATION_FAILED")

    def test_manual_verify_completes_recovered_plan(self):
        with TemporaryDirectory() as directory:
            service, store, incidents, _, _ = self._service(
                directory,
                resolve_on_scan=False,
            )
            incident = self._incident(store)
            store.update_runtime("B64", {"phase": "READY", "active_leases": 0})
            store.update_runtime("B68", {"phase": "STOPPED", "running": False})
            plan = service.plan_latest()["plan"]
            records = list(reversed(store.list_records("B69", limit=100)))
            records[0]["status"] = "RESOLVED"
            store.replace_records("B69", records)
            incidents.resolve_on_scan = False
            result = service.verify_latest()
            self.assertEqual(result["status"], "AUTONOMOUS_RECOVERY_VERIFIED")
            self.assertEqual(result["plan"]["recovery_id"], plan["recovery_id"])
            self.assertEqual(result["plan"]["status"], "COMPLETED")
            self.assertEqual(incident["incident_id"], result["plan"]["incident_id"])

    def test_attempt_limit_escalates(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(directory)
            self._incident(store)
            plan = service.plan_latest()["plan"]
            store.update_policy("B70", {"max_attempts_per_incident": 1})
            chronological = list(reversed(store.list_records("B70", limit=100)))
            chronological[0]["attempts"] = 1
            store.replace_records("B70", chronological)
            result = service.execute_latest()
            self.assertEqual(
                result["status"],
                "AUTONOMOUS_RECOVERY_ATTEMPTS_EXHAUSTED",
            )
            self.assertEqual(result["plan"]["recovery_id"], plan["recovery_id"])
            self.assertEqual(result["decision"], "ESCALATE")

    def test_cycle_scans_and_plans_but_never_executes(self):
        with TemporaryDirectory() as directory:
            service, store, incidents, budget, full = self._service(
                directory,
                resolve_on_scan=False,
            )
            self._incident(store)
            result = service.run_cycle()
            self.assertEqual(result["status"], "AUTONOMOUS_RECOVERY_CYCLE_PLANNED")
            self.assertEqual(result["plan"]["status"], "PREVIEW_READY")
            incidents.scan.assert_called_once()
            full.stop_background.assert_not_called()
            budget.release_owner_leases.assert_not_called()
            self.assertFalse(store.policy("B70")["auto_execute_safe"])

    def test_clear_cycle_records_ready_state(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(directory)
            result = service.run_cycle()
            self.assertEqual(result["status"], "AUTONOMOUS_RECOVERY_CYCLE_CLEAR")
            self.assertEqual(result["decision"], "CLEAR")
            self.assertEqual(store.runtime("B70")["cycles_completed"], 1)

    def test_start_stop_background_persists_policy(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(directory)
            with patch.object(service, "run_cycle", return_value={"success": True}):
                started = service.start_background()
                self.assertTrue(started["success"])
                time.sleep(0.03)
                stopped = service.stop_background()
            self.assertEqual(
                stopped["status"],
                "AUTONOMOUS_RECOVERY_SUPERVISOR_STOPPED",
            )
            self.assertFalse(store.policy("B70")["enabled"])
            self.assertFalse(store.policy("B70")["auto_execute_safe"])
            self.assertFalse(store.policy("B70")["auto_approve"])

    def test_restart_reconciles_running_state(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            store.update_runtime("B70", {
                "running": True,
                "phase": "MONITORING",
            })
            AutonomousRecoveryOrchestratorService(
                directory,
                store=store,
                incident_response=FakeIncidentResponse(store),
                resource_budget=FakeBudget(store),
                full_autonomy=FakeFullAutonomy(store),
            )
            runtime = store.runtime("B70")
            self.assertFalse(runtime["running"])
            self.assertEqual(runtime["phase"], "RECOVERED_AFTER_RESTART")

    def test_status_finalizes_pending_worker(self):
        with TemporaryDirectory() as directory:
            service, store, _, _, _ = self._service(directory)
            store.update_runtime("B70", {
                "running": False,
                "phase": "STOPPED_PENDING_WORKER",
            })
            result = service.status()
            self.assertEqual(result["runtime"]["phase"], "STOPPED")

    def test_router_recognizes_b70_commands(self):
        router = SoftwareEngineerAutonomyGovernanceRouter()
        commands = (
            "Pokaż status odzyskiwania autonomii",
            "Przygotuj plan odzyskiwania",
            "Wykonaj bezpieczne odzyskiwanie",
            "Zweryfikuj odzyskiwanie",
            "Uruchom orkiestrator odzyskiwania",
        )
        for command in commands:
            self.assertTrue(router.can_handle(command), command)
        self.assertEqual(
            router._action("", "pokaż status b62-b70"),
            "suite_status",
        )
        self.assertEqual(
            router._action("", "pokaż status odzyskiwania autonomii"),
            "b70_status",
        )

    def test_controller_gate_recognizes_b70(self):
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(
            "Pokaż status odzyskiwania autonomii"
        ))

    def test_safety_classifies_status_and_execution(self):
        self.assertTrue(is_read_only_learning_command(
            "Pokaż status odzyskiwania autonomii"
        ))
        self.assertFalse(is_read_only_learning_command(
            "Wykonaj bezpieczne odzyskiwanie"
        ))
        self.assertFalse(is_read_only_learning_command(
            "Uruchom orkiestrator odzyskiwania"
        ))

    def test_formatter_reports_plan_and_manual_execution(self):
        text = format_autonomy_governance_response({
            "status": "AUTONOMOUS_RECOVERY_STATUS",
            "stage": "B70",
            "runtime": {"phase": "PREVIEW_READY", "cycles_completed": 2},
            "policy": {"auto_approve": False},
            "summary": {},
            "plan_counts": {"preview_ready": 1, "completed": 2},
            "plans": [{
                "recovery_id": "recovery-1",
                "status": "PREVIEW_READY",
                "category": "ORPHANED_B68_LEASE",
                "steps": ["STOP_B68", "RELEASE_B68_LEASES"],
            }],
        })
        self.assertIn("B70", text)
        self.assertIn("ORPHANED_B68_LEASE", text)
        self.assertIn("jawnego potwierdzenia", text)
        self.assertIn("auto-approve NIE", text)

    def test_suite_status_includes_b70_without_breaking_legacy_stage(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            dummy = SimpleNamespace()
            suite = AutonomyGovernanceSuite(
                directory,
                store=store,
                safe_policy_deployment=dummy,
                goal_governance=dummy,
                resource_budget=dummy,
                causal_learning=dummy,
                release_manager=dummy,
                self_maintenance=dummy,
                full_autonomy=dummy,
                incident_response=dummy,
                recovery_orchestrator=dummy,
            )
            result = suite.status()
            self.assertEqual(result["stage"], "B62-B69")
            self.assertEqual(result["suite_span"], "B62-B70")
            self.assertIn("B70", result["stage_summaries"])

    def test_brain_formatter_routes_b70(self):
        text = BrainResponseFormatter()._format_software_engineer_response({
            "operation": "autonomy_governance_suite",
            "stage": "B70",
            "status": "AUTONOMOUS_RECOVERY_STATUS",
            "runtime": {},
            "policy": {},
            "summary": {},
            "plans": [],
        })
        self.assertIn("B70", text)

    def test_source_limits_remain_bounded(self):
        project = Path(__file__).resolve().parents[1]
        limits = {
            "app/ai/software_engineer/autonomous_recovery_orchestrator_service.py": 800,
            "app/ai/software_engineer/autonomy_governance_store.py": 440,
            "app/ai/software_engineer/software_engineer_autonomy_governance_router.py": 440,
            "app/ai/software_engineer/autonomous_software_engineer.py": 440,
        }
        for relative, limit in limits.items():
            lines = (project / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, relative)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import time
import unittest
from unittest.mock import MagicMock, patch

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_incident_response_service import (
    AutonomousIncidentResponseService,
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


class FakeBudget:
    def __init__(self) -> None:
        self.release_owner_leases = MagicMock(return_value={
            "success": True,
            "status": "RESOURCE_BUDGET_OWNER_LEASES_RELEASED",
            "released_count": 1,
        })

    def status(self):
        return {
            "success": True,
            "status": "RESOURCE_BUDGET_STATUS",
        }


class FakeFullAutonomy:
    def __init__(self) -> None:
        self.stop_background = MagicMock(return_value={
            "success": True,
            "status": "FULL_24X7_AUTONOMY_STOPPED",
        })


class B69AutonomousIncidentResponseTests(unittest.TestCase):
    def _service(self, directory):
        store = AutonomyGovernanceStore(directory)
        store.update_policy("B69", {
            "enabled": True,
            "auto_approve": True,
        })
        budget = FakeBudget()
        full = FakeFullAutonomy()
        service = AutonomousIncidentResponseService(
            directory,
            store=store,
            resource_budget=budget,
            full_autonomy=full,
        )
        return service, store, budget, full

    def test_b69_policy_is_bounded_and_never_auto_approves(self):
        policy = harden_stage_policy("B69", {
            "enabled": True,
            "auto_approve": True,
            "interval_seconds": 1,
            "max_incidents": 999999,
            "stage_failure_threshold": 0,
        })
        self.assertFalse(policy["auto_approve"])
        self.assertEqual(policy["interval_seconds"], 30.0)
        self.assertEqual(policy["max_incidents"], 10000)
        self.assertEqual(policy["stage_failure_threshold"], 1)

    def test_store_persists_b69_incidents(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            item = store.append_record("B69", {
                "incident_id": "i1",
                "status": "OPEN",
                "severity": "HIGH",
            })
            self.assertEqual(item["stage"], "B69")
            self.assertEqual(store.list_records("B69")[0]["incident_id"], "i1")
            self.assertIn("B69", store.compact())

    def test_one_shot_scan_works_while_background_disabled(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            service = AutonomousIncidentResponseService(
                directory,
                store=store,
                resource_budget=FakeBudget(),
                full_autonomy=FakeFullAutonomy(),
            )
            self.assertFalse(store.policy("B69")["enabled"])
            result = service.scan()
            self.assertEqual(result["status"], "AUTONOMOUS_INCIDENT_SCAN_COMPLETED")
            self.assertEqual(result["detected"], 0)
            self.assertFalse(result["policy"]["enabled"])

    def test_clear_scan_records_no_incident(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            result = service.scan()
            self.assertEqual(result["status"], "AUTONOMOUS_INCIDENT_SCAN_COMPLETED")
            self.assertEqual(result["detected"], 0)
            self.assertEqual(result["decision"], "CLEAR")
            self.assertEqual(store.runtime("B69")["cycles_completed"], 1)

    def test_critical_lease_overflow_is_auto_contained(self):
        with TemporaryDirectory() as directory:
            service, store, budget, full = self._service(directory)
            store.update_runtime("B64", {
                "phase": "LEASED",
                "active_leases": 2,
            })
            store.update_runtime("B68", {
                "running": True,
                "phase": "RUNNING",
            })
            result = service.scan()
            categories = {item["category"] for item in result["incidents"]}
            self.assertIn("RESOURCE_LEASE_OVERFLOW", categories)
            self.assertTrue(result["contained"])
            full.stop_background.assert_called()
            budget.release_owner_leases.assert_called_with(
                "B68",
                success=False,
                reason=unittest.mock.ANY,
            )
            self.assertFalse(store.policy("B68")["auto_approve"])

    def test_orphaned_lease_is_critical(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            store.update_runtime("B64", {
                "phase": "LEASED",
                "active_leases": 1,
            })
            store.update_runtime("B68", {
                "running": False,
                "phase": "STOPPED",
            })
            result = service.scan()
            categories = {item["category"] for item in result["incidents"]}
            self.assertIn("ORPHANED_B68_LEASE", categories)

    def test_duplicate_signal_updates_existing_incident(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            store.update_policy("B69", {"auto_contain_critical": False})
            store.update_runtime("B68", {
                "phase": "CYCLE_TIMEOUT",
                "last_error": "timeout",
            })
            service.scan()
            service.scan()
            records = store.list_records("B69", limit=50)
            timeout_records = [
                item for item in records
                if item.get("category") == "B68_CYCLE_TIMEOUT"
            ]
            self.assertEqual(len(timeout_records), 1)
            self.assertEqual(timeout_records[0]["occurrences"], 2)

    def test_recovered_signal_is_auto_resolved(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            store.update_policy("B69", {"auto_contain_critical": False})
            store.update_runtime("B68", {"phase": "CYCLE_TIMEOUT"})
            service.scan()
            store.update_runtime("B68", {
                "phase": "STOPPED",
                "last_error": "",
            })
            result = service.scan()
            self.assertTrue(result["resolved"])
            self.assertEqual(
                store.list_records("B69", limit=10)[0]["status"],
                "RESOLVED",
            )

    def test_high_incident_is_not_auto_contained(self):
        with TemporaryDirectory() as directory:
            service, store, budget, full = self._service(directory)
            store.update_runtime("B63", {
                "consecutive_failures": 2,
                "last_error": "bad goals",
            })
            result = service.scan()
            self.assertEqual(result["decision"], "OBSERVE")
            self.assertFalse(result["contained"])
            full.stop_background.assert_not_called()
            budget.release_owner_leases.assert_not_called()

    def test_manual_containment_handles_latest_high_incident(self):
        with TemporaryDirectory() as directory:
            service, store, budget, full = self._service(directory)
            store.update_runtime("B63", {"consecutive_failures": 2})
            service.scan()
            result = service.contain_latest()
            self.assertEqual(result["status"], "AUTONOMOUS_INCIDENT_CONTAINED")
            self.assertEqual(result["incident"]["status"], "CONTAINED")
            full.stop_background.assert_called_once()
            budget.release_owner_leases.assert_called_once()

    def test_manual_resolution_closes_latest_incident(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            store.update_runtime("B63", {"consecutive_failures": 2})
            service.scan()
            result = service.resolve_latest()
            self.assertEqual(result["status"], "AUTONOMOUS_INCIDENT_RESOLVED")
            self.assertEqual(result["incident"]["status"], "RESOLVED")

    def test_status_reports_incident_counts(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            store.append_record("B69", {
                "incident_id": "open",
                "status": "OPEN",
                "severity": "CRITICAL",
            })
            store.append_record("B69", {
                "incident_id": "done",
                "status": "RESOLVED",
                "severity": "HIGH",
            })
            result = service.status()
            self.assertEqual(result["incident_counts"]["open"], 1)
            self.assertEqual(result["incident_counts"]["resolved"], 1)
            self.assertEqual(result["incident_counts"]["critical"], 1)

    def test_status_finalizes_pending_worker_after_exit(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            store.update_runtime("B69", {
                "running": False,
                "phase": "STOPPED_PENDING_WORKER",
            })
            result = service.status()
            self.assertEqual(result["runtime"]["phase"], "STOPPED")

    def test_restart_reconciles_running_flag(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            store.update_runtime("B69", {
                "running": True,
                "phase": "MONITORING",
            })
            AutonomousIncidentResponseService(
                directory,
                store=store,
                resource_budget=FakeBudget(),
                full_autonomy=FakeFullAutonomy(),
            )
            runtime = store.runtime("B69")
            self.assertFalse(runtime["running"])
            self.assertEqual(runtime["phase"], "RECOVERED_AFTER_RESTART")

    def test_start_and_stop_background_are_persistent(self):
        with TemporaryDirectory() as directory:
            service, store, _, _ = self._service(directory)
            with patch.object(service, "scan", return_value={"success": True}):
                started = service.start_background()
                self.assertTrue(started["success"])
                time.sleep(0.03)
                stopped = service.stop_background()
            self.assertEqual(stopped["status"], "AUTONOMOUS_INCIDENT_MONITOR_STOPPED")
            self.assertFalse(store.policy("B69")["enabled"])
            self.assertFalse(store.policy("B69")["auto_approve"])
            self.assertFalse(service.is_running())

    def test_router_recognizes_b69_commands(self):
        router = SoftwareEngineerAutonomyGovernanceRouter()
        commands = (
            "Pokaż status centrum incydentów",
            "Uruchom monitor incydentów",
            "Przeprowadź skan incydentów",
            "Ogranicz ostatni incydent",
            "Zamknij ostatni incydent",
        )
        for command in commands:
            self.assertTrue(router.can_handle(command), command)
        self.assertEqual(
            router._action("", "pokaż status b62-b69"),
            "suite_status",
        )
        self.assertEqual(
            router._action("", "pokaż status centrum incydentów"),
            "b69_status",
        )

    def test_controller_gate_recognizes_b69(self):
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(
            "Pokaż status centrum incydentów"
        ))

    def test_safety_classifies_status_and_mutation(self):
        self.assertTrue(is_read_only_learning_command(
            "Pokaż status centrum incydentów"
        ))
        self.assertFalse(is_read_only_learning_command(
            "Uruchom monitor incydentów"
        ))
        self.assertFalse(is_read_only_learning_command(
            "Ogranicz ostatni incydent"
        ))

    def test_formatter_reports_b69_incidents_and_safety(self):
        text = format_autonomy_governance_response({
            "status": "AUTONOMOUS_INCIDENT_RESPONSE_STATUS",
            "stage": "B69",
            "runtime": {"phase": "READY", "cycles_completed": 2},
            "policy": {"auto_approve": False},
            "summary": {},
            "incident_counts": {"open": 1, "contained": 1, "resolved": 2},
            "incidents": [{
                "severity": "CRITICAL",
                "status": "CONTAINED",
                "category": "ORPHANED_B68_LEASE",
                "stage_name": "B64",
            }],
        })
        self.assertIn("B69", text)
        self.assertIn("otwarte 1", text)
        self.assertIn("ORPHANED_B68_LEASE", text)
        self.assertIn("auto-approve NIE", text)

    def test_suite_status_includes_b69(self):
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
            )
            result = suite.status()
            self.assertEqual(result["stage"], "B62-B69")
            self.assertIn("B69", result["stage_summaries"])

    def test_brain_formatter_routes_b69(self):
        text = BrainResponseFormatter()._format_software_engineer_response({
            "operation": "autonomy_governance_suite",
            "stage": "B69",
            "status": "AUTONOMOUS_INCIDENT_RESPONSE_STATUS",
            "runtime": {},
            "policy": {},
            "summary": {},
            "incidents": [],
        })
        self.assertIn("B69", text)

    def test_source_limits_remain_bounded(self):
        project = Path(__file__).resolve().parents[1]
        limits = {
            "app/ai/software_engineer/autonomous_incident_response_service.py": 800,
            "app/ai/software_engineer/autonomy_governance_store.py": 440,
            "app/ai/software_engineer/software_engineer_autonomy_governance_router.py": 440,
        }
        for relative, limit in limits.items():
            lines = (project / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, relative)


if __name__ == "__main__":
    unittest.main()

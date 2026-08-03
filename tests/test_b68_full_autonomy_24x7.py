from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomy_governance_store import AutonomyGovernanceStore
from app.ai.software_engineer.full_autonomy_24x7_service import FullAutonomy24x7Service
from app.ai.software_engineer.software_engineer_autonomy_governance_formatter import format_autonomy_governance_response
from app.ai.software_engineer.software_engineer_autonomy_governance_router import SoftwareEngineerAutonomyGovernanceRouter
from app.ai.software_engineer.autonomous_software_engineer import AutonomousSoftwareEngineerController
from app.gui.command_safety import is_read_only_learning_command


class FakeResource:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.release = MagicMock(return_value={"success": True})

    def acquire(self, owner):
        if not self.allowed:
            return {"success": True, "allowed": False, "status": "RESOURCE_BUDGET_DEFERRED", "reasons": ["CPU_LIMIT"]}
        return {"success": True, "allowed": True, "status": "RESOURCE_BUDGET_LEASE_GRANTED", "lease": {"lease_id": "l1"}}

    def status(self):
        return {"success": True, "status": "RESOURCE_BUDGET_STATUS"}


def service_result(status="OK"):
    return {"success": True, "status": status}


class B68FullAutonomyTests(unittest.TestCase):
    def _service(self, directory, allowed=True, active=0, waiting=0):
        store = AutonomyGovernanceStore(directory)
        store.update_policy("B68", {"enabled": True})
        store.update_runtime("B68", {"enabled": True})
        execution_store = MagicMock()
        execution_store.summary.return_value = {
            "active": active, "waiting_approval": waiting, "completed": 0
        }
        execution = SimpleNamespace(
            store=execution_store,
            reconcile=MagicMock(return_value=service_result("RECONCILED")),
            dispatch_next=MagicMock(return_value=service_result("DISPATCHED")),
        )
        keyword = dict(
            project_root=directory,
            store=store,
            resource_budget=FakeResource(allowed),
            project_intelligence=SimpleNamespace(run_cycle=MagicMock(return_value=service_result("B55"))),
            self_directed=SimpleNamespace(),
            strategic_development=SimpleNamespace(run_cycle=MagicMock(return_value=service_result("B57"))),
            strategic_execution=execution,
            strategic_portfolio=SimpleNamespace(rebalance=MagicMock(return_value=service_result("B59"))),
            strategic_policy_evolution=SimpleNamespace(learn=MagicMock(return_value=service_result("B60"))),
            strategic_policy_validation=SimpleNamespace(run_cycle=MagicMock(return_value=service_result("B61"))),
            safe_policy_deployment=SimpleNamespace(run_cycle=MagicMock(return_value=service_result("B62"))),
            goal_governance=SimpleNamespace(run_cycle=MagicMock(return_value=service_result("B63"))),
            causal_learning=SimpleNamespace(run_cycle=MagicMock(return_value=service_result("B65"))),
            release_manager=SimpleNamespace(run_cycle=MagicMock(return_value=service_result("B66"))),
            self_maintenance=SimpleNamespace(scan=MagicMock(return_value=service_result("B67"))),
        )
        return FullAutonomy24x7Service(**keyword), execution

    def test_cycle_runs_integrated_chain(self):
        with TemporaryDirectory() as directory:
            service, execution = self._service(directory)
            result = service.run_cycle()
            self.assertEqual(result["status"], "FULL_24X7_AUTONOMY_CYCLE_COMPLETED")
            self.assertIn("B62", result["steps"])
            self.assertIn("B67", result["steps"])
            execution.dispatch_next.assert_called_once()

    def test_waiting_approval_blocks_dispatch(self):
        with TemporaryDirectory() as directory:
            service, execution = self._service(directory, waiting=1)
            result = service.run_cycle()
            self.assertEqual(result["steps"]["B58_DISPATCH"]["status"], "FULL_24X7_DISPATCH_HELD")
            execution.dispatch_next.assert_not_called()

    def test_resource_limits_defer_cycle(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory, allowed=False)
            result = service.run_cycle()
            self.assertEqual(result["status"], "FULL_24X7_AUTONOMY_DEFERRED_RESOURCES")

    def test_pause_and_resume_persist(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory)
            service.pause()
            self.assertTrue(service.store.runtime("B68")["paused"])
            with patch.object(service, "start_background", return_value={"success": True}) as start:
                service.resume()
                start.assert_called_once()

    def test_stop_disables_policy(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory)
            service.stop_background()
            self.assertFalse(service.store.policy("B68")["enabled"])

    def test_policy_never_auto_approves(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory)
            result = service.update_policy({"auto_approve": True})
            self.assertFalse(result["policy"]["auto_approve"])

    def test_router_recognizes_all_suite_stages(self):
        router = SoftwareEngineerAutonomyGovernanceRouter()
        for command in (
            "Pokaż status wdrażania polityki",
            "Przeprowadź audyt celów",
            "Pokaż status budżetu autonomii",
            "Przeprowadź analizę przyczynową",
            "Utwórz kandydata wydania",
            "Przeskanuj konserwację projektu",
            "Pokaż status autonomii 24/7",
        ):
            self.assertTrue(router.can_handle(command), command)


    def test_suite_status_phrase_has_precedence_over_b62(self):
        router = SoftwareEngineerAutonomyGovernanceRouter()
        self.assertEqual(
            router._action("", "pokaż status b62-b68"),
            "suite_status",
        )

    def test_controller_gate_recognizes_b68(self):
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(
            "Pokaż status autonomii 24/7"
        ))

    def test_read_only_and_mutating_safety(self):
        self.assertTrue(is_read_only_learning_command("Pokaż status autonomii 24/7"))
        self.assertFalse(is_read_only_learning_command("Uruchom autonomię 24/7"))

    def test_formatter_reports_global_safety(self):
        text = format_autonomy_governance_response({
            "status": "FULL_24X7_AUTONOMY_STATUS",
            "stage": "B68",
            "runtime": {"phase": "READY", "cycles_completed": 1},
            "policy": {"max_daily_cycles": 24},
            "summary": {},
        })
        self.assertIn("B68", text)
        self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_suite(self):
        text = BrainResponseFormatter()._format_software_engineer_response({
            "operation": "autonomy_governance_suite",
            "stage": "B62-B68",
            "status": "AUTONOMY_GOVERNANCE_SUITE_STATUS",
            "runtime": {}, "policy": {}, "summary": {},
        })
        self.assertIn("B62-B68", text)

    def test_source_limits_stay_bounded(self):
        project = Path(__file__).resolve().parents[1]
        self.assertLess(len((project / "app/ai/brain.py").read_text(encoding="utf-8").splitlines()), 1000)
        self.assertLess(len((project / "app/ai/software_engineer/autonomous_software_engineer.py").read_text(encoding="utf-8").splitlines()), 440)
        self.assertLess(len((project / "app/ai/software_engineer/software_engineer_advanced_change_router.py").read_text(encoding="utf-8").splitlines()), 360)
        self.assertLess(len((project / "app/ai/software_engineer/full_autonomy_24x7_service.py").read_text(encoding="utf-8").splitlines()), 800)


if __name__ == "__main__":
    unittest.main()

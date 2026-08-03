from __future__ import annotations

from tempfile import TemporaryDirectory
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomy_governance_store import (
    AutonomyGovernanceStore,
)
from app.ai.software_engineer.full_autonomy_24x7_service import (
    FullAutonomy24x7Service,
)
from app.ai.software_engineer.resource_budget_service import (
    ResourceBudgetService,
)


def _ok(status: str):
    return {"success": True, "status": status}


class _AliveThread:
    def __init__(self) -> None:
        self.joined = False

    def is_alive(self) -> bool:
        return True

    def join(self, timeout=None) -> None:
        self.joined = True


class B681StuckLeaseRecoveryTests(unittest.TestCase):
    def _resource(self, directory, store):
        return ResourceBudgetService(
            directory,
            store=store,
            metric_provider=lambda: {
                "cpu_percent": 10.0,
                "ram_percent": 20.0,
                "free_disk_gb": 100.0,
            },
        )

    def _service(self, directory, store, resource, *, b57=None):
        execution_store = MagicMock()
        execution_store.summary.return_value = {
            "active": 0,
            "waiting_approval": 0,
            "completed": 0,
        }
        execution = SimpleNamespace(
            store=execution_store,
            reconcile=MagicMock(return_value=_ok("B58_RECONCILED")),
            dispatch_next=MagicMock(return_value=_ok("B58_DISPATCHED")),
        )
        return FullAutonomy24x7Service(
            directory,
            store=store,
            resource_budget=resource,
            project_intelligence=SimpleNamespace(
                run_cycle=MagicMock(return_value=_ok("B55"))
            ),
            self_directed=SimpleNamespace(),
            strategic_development=SimpleNamespace(
                run_cycle=b57 or MagicMock(return_value=_ok("B57"))
            ),
            strategic_execution=execution,
            strategic_portfolio=SimpleNamespace(
                rebalance=MagicMock(return_value=_ok("B59"))
            ),
            strategic_policy_evolution=SimpleNamespace(
                learn=MagicMock(return_value=_ok("B60"))
            ),
            strategic_policy_validation=SimpleNamespace(
                run_cycle=MagicMock(return_value=_ok("B61"))
            ),
            safe_policy_deployment=SimpleNamespace(
                run_cycle=MagicMock(return_value=_ok("B62"))
            ),
            goal_governance=SimpleNamespace(
                run_cycle=MagicMock(return_value=_ok("B63"))
            ),
            causal_learning=SimpleNamespace(
                run_cycle=MagicMock(return_value=_ok("B65"))
            ),
            release_manager=SimpleNamespace(
                run_cycle=MagicMock(return_value=_ok("B66"))
            ),
            self_maintenance=SimpleNamespace(
                scan=MagicMock(return_value=_ok("B67"))
            ),
        )

    def test_owner_recovery_releases_active_lease(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            resource.acquire("B68")
            result = resource.release_owner_leases(
                "B68",
                reason="test recovery",
            )
            self.assertEqual(result["released_count"], 1)
            self.assertEqual(store.runtime("B64")["active_leases"], 0)
            self.assertEqual(store.runtime("B64")["phase"], "READY")

    def test_status_repairs_stale_runtime_counter(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            store.update_runtime("B64", {
                "phase": "LEASED",
                "active_leases": 1,
            })
            result = resource.status()
            self.assertEqual(result["runtime"]["active_leases"], 0)
            self.assertEqual(result["runtime"]["phase"], "READY")

    def test_service_initialization_recovers_orphaned_b68_lease(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            resource.acquire("B68")
            self._service(directory, store, resource)
            self.assertEqual(store.runtime("B64")["active_leases"], 0)

    def test_stop_recovers_lease_when_worker_does_not_join(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            service = self._service(directory, store, resource)
            resource.acquire("B68")
            service._thread = _AliveThread()
            result = service.stop_background()
            self.assertTrue(result["worker_alive"])
            self.assertEqual(store.runtime("B64")["active_leases"], 0)
            self.assertEqual(
                store.runtime("B68")["phase"],
                "STOPPED_PENDING_WORKER",
            )

    def test_cycle_records_current_step_and_releases_lease(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            seen = []

            def b57():
                seen.append(store.runtime("B68")["phase"])
                return _ok("B57")

            service = self._service(directory, store, resource, b57=b57)
            store.update_policy("B68", {"enabled": True})
            store.update_runtime("B68", {"enabled": True})
            result = service.run_cycle()
            self.assertEqual(result["status"], "FULL_24X7_AUTONOMY_CYCLE_COMPLETED")
            self.assertEqual(seen, ["RUNNING_B57"])
            self.assertEqual(store.runtime("B64")["active_leases"], 0)

    def test_watchdog_disables_b68_and_recovers_lease(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            service = self._service(directory, store, resource)
            lease = resource.acquire("B68")["lease"]
            token = "cycle-timeout-test"
            done = threading.Event()
            service._activate_cycle(token, lease["lease_id"], done)
            service._watch_cycle(token, lease["lease_id"], done, 0.01)
            self.assertEqual(store.runtime("B64")["active_leases"], 0)
            self.assertEqual(store.runtime("B68")["phase"], "CYCLE_TIMEOUT")
            self.assertFalse(store.policy("B68")["enabled"])


if __name__ == "__main__":
    unittest.main()

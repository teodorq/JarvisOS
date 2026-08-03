from __future__ import annotations

from tempfile import TemporaryDirectory
from types import SimpleNamespace
import threading
import time
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


class B683WorkerFinalizationTests(unittest.TestCase):
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
        strategic_development = b57 or SimpleNamespace(
            is_running=MagicMock(return_value=False),
            run_cycle=MagicMock(return_value=_ok("B57")),
        )
        return FullAutonomy24x7Service(
            directory,
            store=store,
            resource_budget=resource,
            project_intelligence=SimpleNamespace(
                run_cycle=MagicMock(return_value=_ok("B55"))
            ),
            self_directed=SimpleNamespace(),
            strategic_development=strategic_development,
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

    def test_initialization_reconciles_stale_pending_worker(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            store.update_policy("B68", {
                "enabled": False,
                "auto_approve": False,
            })
            store.update_runtime("B68", {
                "enabled": False,
                "running": False,
                "phase": "STOPPED_PENDING_WORKER",
                "last_error": "stale",
            })
            resource = self._resource(directory, store)
            self._service(directory, store, resource)
            runtime = store.runtime("B68")
            self.assertEqual(runtime["phase"], "STOPPED")
            self.assertEqual(runtime["last_error"], "")
            self.assertFalse(store.policy("B68")["auto_approve"])

    def test_run_loop_finally_promotes_pending_worker_to_stopped(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            service = self._service(directory, store, resource)
            store.update_runtime("B68", {
                "running": False,
                "phase": "STOPPED_PENDING_WORKER",
            })
            service._stop_event.set()
            service._run_loop()
            runtime = store.runtime("B68")
            self.assertEqual(runtime["phase"], "STOPPED")
            self.assertEqual(
                runtime["last_status"],
                "FULL_24X7_AUTONOMY_STOPPED",
            )

    def test_worker_finalizer_updates_phase_after_worker_exits(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            service = self._service(directory, store, resource)
            release = threading.Event()

            def delayed_worker():
                release.wait(3.0)

            worker = threading.Thread(target=delayed_worker, daemon=True)
            worker.start()
            service._thread = worker
            service._stop_event.set()
            store.update_policy("B68", {
                "enabled": False,
                "auto_approve": False,
            })
            store.update_runtime("B68", {
                "enabled": False,
                "running": False,
                "phase": "STOPPED_PENDING_WORKER",
            })
            service._start_worker_finalizer(worker)
            release.set()
            finalizer = service._worker_finalizer
            self.assertIsNotNone(finalizer)
            finalizer.join(timeout=3.0)
            self.assertFalse(finalizer.is_alive())
            self.assertEqual(store.runtime("B68")["phase"], "STOPPED")
            self.assertFalse(service.is_running())

    def test_active_b57_supervisor_is_observed_not_called(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            b57 = SimpleNamespace(
                is_running=MagicMock(return_value=True),
                run_cycle=MagicMock(return_value=_ok("B57")),
            )
            service = self._service(
                directory,
                store,
                resource,
                b57=b57,
            )
            store.update_policy("B68", {"enabled": True})
            store.update_runtime("B68", {"enabled": True})
            result = service.run_cycle()
            self.assertEqual(
                result["steps"]["B57"]["status"],
                "FULL_24X7_STEP_B57_DELEGATED",
            )
            b57.run_cycle.assert_not_called()
            self.assertEqual(store.runtime("B64")["active_leases"], 0)

    def test_status_repairs_pending_state_after_worker_finished(self):
        with TemporaryDirectory() as directory:
            store = AutonomyGovernanceStore(directory)
            resource = self._resource(directory, store)
            service = self._service(directory, store, resource)
            store.update_runtime("B68", {
                "enabled": False,
                "running": False,
                "phase": "STOPPED_PENDING_WORKER",
            })
            result = service.status()
            self.assertEqual(result["runtime"]["phase"], "STOPPED")


if __name__ == "__main__":
    unittest.main()

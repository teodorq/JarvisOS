from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.ai.software_engineer.autonomy_governance_store import AutonomyGovernanceStore
from app.ai.software_engineer.resource_budget_service import ResourceBudgetService


class B64ResourceBudgetTests(unittest.TestCase):
    def _service(self, directory, **metrics):
        values = {"cpu_percent": 10.0, "ram_percent": 20.0, "free_disk_gb": 100.0}
        values.update(metrics)
        store = AutonomyGovernanceStore(directory)
        return ResourceBudgetService(
            directory,
            store=store,
            metric_provider=lambda: values,
        ), store

    def test_safe_metrics_grant_single_lease(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory)
            result = service.acquire("test")
            self.assertTrue(result["allowed"])
            self.assertEqual(result["status"], "RESOURCE_BUDGET_LEASE_GRANTED")

    def test_second_active_lease_is_deferred(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory)
            service.acquire("one")
            result = service.acquire("two")
            self.assertFalse(result["allowed"])
            self.assertIn("ACTIVE_LEASE_LIMIT", result["reasons"])

    def test_cpu_limit_defers(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory, cpu_percent=99.0)
            result = service.acquire()
            self.assertIn("CPU_LIMIT", result["reasons"])

    def test_ram_limit_defers(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory, ram_percent=99.0)
            self.assertIn("RAM_LIMIT", service.acquire()["reasons"])

    def test_disk_limit_defers(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory, free_disk_gb=0.1)
            self.assertIn("DISK_LIMIT", service.acquire()["reasons"])

    def test_release_closes_lease(self):
        with TemporaryDirectory() as directory:
            service, store = self._service(directory)
            lease = service.acquire()["lease"]
            service.release(lease["lease_id"])
            self.assertEqual(store.runtime("B64")["active_leases"], 0)

    def test_failure_circuit_opens_and_resets(self):
        with TemporaryDirectory() as directory:
            service, store = self._service(directory)
            for _ in range(3):
                lease = service.acquire()["lease"]
                service.release(lease["lease_id"], success=False, reason="x")
            result = service.acquire()
            self.assertIn("FAILURE_CIRCUIT_OPEN", result["reasons"])
            service.reset_failure_circuit()
            self.assertEqual(store.runtime("B64")["consecutive_failures"], 0)

    def test_policy_hardens_active_limit_and_auto_approve(self):
        with TemporaryDirectory() as directory:
            service, _ = self._service(directory)
            result = service.update_policy({"max_active_leases": 99, "auto_approve": True})
            self.assertEqual(result["policy"]["max_active_leases"], 1)
            self.assertFalse(result["policy"]["auto_approve"])


if __name__ == "__main__":
    unittest.main()

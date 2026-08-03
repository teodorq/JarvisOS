from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.ai.software_engineer.autonomy_governance_store import AutonomyGovernanceStore
from app.ai.software_engineer.safe_policy_deployment_service import SafePolicyDeploymentService
from tests.b62_b68_fakes import FakeValidation, MemoryExecutionStore


class B62SafePolicyDeploymentTests(unittest.TestCase):
    def _service(self, directory, records=None, experiments=None):
        store = AutonomyGovernanceStore(directory)
        execution_store = MemoryExecutionStore(records)
        validation = FakeValidation(experiments, execution_store)
        service = SafePolicyDeploymentService(
            directory,
            store=store,
            strategic_policy_validation=validation,
        )
        return service, validation, store

    def test_no_candidate_is_safe_hold(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory)
            result = service.run_cycle()
            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "SAFE_POLICY_DEPLOYMENT_NO_CANDIDATE")
            self.assertEqual(result["decision"], "HOLD")

    def test_promoted_experiment_starts_canary(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory, experiments=[{
                "experiment_id": "e1", "revision_id": "r1", "status": "PROMOTED"
            }])
            result = service.run_cycle()
            self.assertEqual(result["status"], "SAFE_POLICY_DEPLOYMENT_CANARY_STARTED")
            self.assertEqual(result["deployment"]["status"], "CANARY")

    def test_canary_waits_for_minimum_observations(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory, experiments=[{
                "experiment_id": "e1", "revision_id": "r1", "status": "PROMOTED"
            }])
            service.run_cycle()
            result = service.run_cycle()
            self.assertEqual(result["status"], "SAFE_POLICY_DEPLOYMENT_CANARY_HOLD")

    def test_canary_activates_after_healthy_observations(self):
        with TemporaryDirectory() as directory:
            records = []
            service, validation, _ = self._service(directory, records=records, experiments=[{
                "experiment_id": "e1", "revision_id": "r1", "status": "PROMOTED"
            }])
            service.run_cycle()
            validation.strategic_execution.store.records.extend([
                {"execution_id": "x1", "status": "COMPLETED"},
                {"execution_id": "x2", "status": "COMPLETED"},
                {"execution_id": "x3", "status": "COMPLETED"},
            ])
            result = service.run_cycle()
            self.assertEqual(result["status"], "SAFE_POLICY_DEPLOYMENT_ACTIVATED")
            self.assertEqual(result["deployment"]["status"], "ACTIVE")

    def test_canary_rolls_back_on_failure_spike(self):
        with TemporaryDirectory() as directory:
            service, validation, _ = self._service(directory, experiments=[{
                "experiment_id": "e1", "revision_id": "r1", "status": "PROMOTED"
            }])
            service.run_cycle()
            validation.strategic_execution.store.records.extend([
                {"execution_id": "x1", "status": "FAILED"},
                {"execution_id": "x2", "status": "FAILED"},
                {"execution_id": "x3", "status": "COMPLETED"},
            ])
            result = service.run_cycle()
            self.assertEqual(result["status"], "SAFE_POLICY_DEPLOYMENT_ROLLED_BACK")
            validation.strategic_policy_evolution.rollback.assert_called_once()

    def test_policy_never_auto_approves(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory)
            result = service.update_policy({"auto_approve": True})
            self.assertFalse(result["policy"]["auto_approve"])

    def test_execution_context_contains_revision(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory)
            context = service.execution_context()
            self.assertEqual(context["strategic_policy_revision_id"], "r1")

    def test_status_reports_b62(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory)
            self.assertEqual(service.status()["stage"], "B62")


if __name__ == "__main__":
    unittest.main()

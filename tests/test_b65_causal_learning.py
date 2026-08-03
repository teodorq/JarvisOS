from __future__ import annotations

from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.ai.software_engineer.autonomy_governance_store import AutonomyGovernanceStore
from app.ai.software_engineer.causal_learning_service import CausalLearningService
from tests.b62_b68_fakes import MemoryExecutionStore


class B65CausalLearningTests(unittest.TestCase):
    def _service(self, directory, records):
        execution = SimpleNamespace(store=MemoryExecutionStore(records))
        return CausalLearningService(
            directory,
            store=AutonomyGovernanceStore(directory),
            strategic_execution=execution,
            safe_policy_deployment=SimpleNamespace(),
        )

    def test_low_evidence_holds(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory, [{"execution_id": "x", "status": "COMPLETED"}])
            result = service.run_cycle()
            self.assertEqual(result["status"], "CAUSAL_LEARNING_INSUFFICIENT_EVIDENCE")

    def test_groups_by_policy_deployment(self):
        records = [
            {"execution_id": f"x{i}", "status": "COMPLETED", "metadata": {"policy_deployment_id": "d1"}}
            for i in range(3)
        ]
        with TemporaryDirectory() as directory:
            result = self._service(directory, records).run_cycle()
            self.assertEqual(result["groups"], 1)
            self.assertEqual(result["hypotheses"][0]["factor"], "d1")

    def test_positive_association_signal(self):
        records = [{"execution_id": f"x{i}", "status": "COMPLETED", "metadata": {"subsystem": "ai"}} for i in range(6)]
        with TemporaryDirectory() as directory:
            result = self._service(directory, records).run_cycle()
            self.assertEqual(result["hypotheses"][0]["signal"], "POSITIVE_ASSOCIATION")

    def test_failure_signal(self):
        records = [{"execution_id": f"x{i}", "status": "FAILED", "metadata": {"subsystem": "ai"}} for i in range(6)]
        with TemporaryDirectory() as directory:
            result = self._service(directory, records).run_cycle()
            self.assertEqual(result["hypotheses"][0]["signal"], "FAILURE_RISK")

    def test_deferred_signal(self):
        records = [{"execution_id": f"x{i}", "status": "DEFERRED_CONSTRAINTS", "metadata": {"subsystem": "ai"}} for i in range(6)]
        with TemporaryDirectory() as directory:
            result = self._service(directory, records).run_cycle()
            self.assertEqual(result["hypotheses"][0]["signal"], "CONSTRAINT_PRESSURE")

    def test_claim_never_asserts_proven_causality(self):
        records = [{"execution_id": f"x{i}", "status": "COMPLETED"} for i in range(6)]
        with TemporaryDirectory() as directory:
            result = self._service(directory, records).run_cycle()
            self.assertEqual(
                result["hypotheses"][0]["claim_scope"],
                "ASSOCIATION_NOT_PROVEN_CAUSATION",
            )

    def test_duplicate_evidence_does_not_duplicate_hypothesis(self):
        records = [{"execution_id": f"x{i}", "status": "COMPLETED"} for i in range(6)]
        with TemporaryDirectory() as directory:
            service = self._service(directory, records)
            first = service.run_cycle()
            second = service.run_cycle()
            self.assertTrue(first["hypotheses"])
            self.assertEqual(second["hypotheses"], [])

    def test_policy_never_auto_approves(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory, [])
            self.assertFalse(service.update_policy({"auto_approve": True})["policy"]["auto_approve"])


if __name__ == "__main__":
    unittest.main()

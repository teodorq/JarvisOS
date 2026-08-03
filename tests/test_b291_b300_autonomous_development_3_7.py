from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from app.ai.software_engineer.deployment_continuity_gate import (
    DeploymentContinuityGate,
)
from app.ai.software_engineer.deployment_receipt_attestation import (
    DeploymentReceiptAttestation,
)
from app.ai.software_engineer.deployment_receipt_ledger import (
    DeploymentReceiptLedger,
)
from app.ai.software_engineer.safe_development_deployment import (
    SafeDevelopmentDeployment,
)
from app.ai.software_engineer.safe_development_models import (
    SafeDevelopmentSession,
)
from app.ai.software_engineer.safe_development_store import SafeDevelopmentStore


class _BlockedContinuity:
    @staticmethod
    def check_deploy(session):
        return {
            "success": False,
            "status": "DEPLOYMENT_BASELINE_MISMATCH",
            "target": session.target,
            "errors": [],
        }


class B291B300AutonomousDevelopment37Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "app").mkdir(parents=True)
        self.ledger = DeploymentReceiptLedger(self.root)
        self.attestation = DeploymentReceiptAttestation(
            self.root,
            ledger=self.ledger,
        )
        self.gate = DeploymentContinuityGate(
            self.root,
            ledger=self.ledger,
            attestation=self.attestation,
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _session(
        self,
        *,
        session_id="safe-dev-continuity0001",
        target="app/continuity.py",
        source_hash=None,
        proposed_hash=None,
        status="READY_FOR_APPROVAL",
        deployment=None,
    ):
        return SafeDevelopmentSession(
            session_id=session_id,
            status=status,
            created_at="2026-08-01T20:00:00+00:00",
            updated_at="2026-08-01T20:00:00+00:00",
            target=target,
            transform="test_transform",
            title="Continuity test",
            rationale="Verify deployment continuity.",
            risk_score=5.0,
            confidence=0.99,
            source_hash=source_hash or "a" * 64,
            proposed_hash=proposed_hash or "b" * 64,
            deployment=dict(deployment or {}),
        )

    def _receipt(
        self,
        *,
        session_id="safe-dev-continuity0001",
        target="app/continuity.py",
        operation="DEPLOY",
        completed_at="2026-08-01T21:00:00+00:00",
        source_hash=None,
        proposed_hash=None,
        backup_hash=None,
        schema_version=1,
        previous_receipt_digest=None,
    ):
        receipt = {
            "schema_version": schema_version,
            "operation": operation,
            "outcome": "DEPLOYED" if operation == "DEPLOY" else "ROLLED_BACK",
            "session_id": session_id,
            "campaign_id": "autodev-work-continuity0001",
            "work_item_id": "work-item-continuity0001",
            "target": target,
            "source_hash": source_hash or "a" * 64,
            "proposed_hash": proposed_hash or "b" * 64,
            "backup_hash": backup_hash or "c" * 64,
            "completed_at": completed_at,
            "validation_success": True,
            "test_count": 17,
            "verified": True,
            "automatic_approval": False,
            "automatic_deployment": False,
        }
        if schema_version == 2:
            receipt["previous_receipt_digest"] = (
                previous_receipt_digest or ""
            )
        receipt["receipt_digest"] = SafeDevelopmentDeployment._receipt_digest(
            receipt
        )
        return receipt

    def _write_runtime(self, receipt, *, source, live):
        target = self.root / receipt["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(live, encoding="utf-8")
        backup = (
            self.root
            / "data/autodev/safe_development_2/backups"
            / receipt["session_id"]
            / "original.py"
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(source, encoding="utf-8")
        receipt["source_hash"] = self._hash(source)
        receipt["proposed_hash"] = self._hash(live)
        receipt["backup_hash"] = hashlib.sha256(
            backup.read_bytes()
        ).hexdigest()
        receipt["receipt_digest"] = SafeDevelopmentDeployment._receipt_digest(
            receipt
        )
        return target, backup

    def test_b291_no_history_is_an_explicit_bootstrap(self):
        session = self._session()
        result = self.gate.check_deploy(session)
        self.assertTrue(result["success"], result)
        self.assertEqual(
            result["status"],
            "DEPLOYMENT_CONTINUITY_BOOTSTRAP",
        )
        self.assertEqual(result["previous_receipt_digest"], "")

    def test_b292_latest_legacy_receipt_defines_deployment_baseline(self):
        receipt = self._receipt()
        self._write_runtime(receipt, source="before\n", live="current\n")
        self.ledger.archive(receipt)
        session = self._session(source_hash=receipt["proposed_hash"])
        result = self.gate.check_deploy(session)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["status"], "DEPLOYMENT_CONTINUITY_VERIFIED")
        self.assertEqual(
            result["previous_receipt_digest"],
            receipt["receipt_digest"],
        )

    def test_b293_manual_drift_cannot_become_a_new_baseline(self):
        receipt = self._receipt()
        self._write_runtime(receipt, source="before\n", live="current\n")
        self.ledger.archive(receipt)
        session = self._session(source_hash=self._hash("manual drift\n"))
        result = self.gate.check_deploy(session)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "DEPLOYMENT_BASELINE_MISMATCH")

    def test_b294_previous_backup_must_still_attest(self):
        receipt = self._receipt()
        _, backup = self._write_runtime(
            receipt,
            source="before\n",
            live="current\n",
        )
        self.ledger.archive(receipt)
        backup.unlink()
        session = self._session(source_hash=receipt["proposed_hash"])
        result = self.gate.check_deploy(session)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "PREVIOUS_DEPLOYMENT_UNHEALTHY")
        self.assertEqual(result["attestation_status"], "BACKUP_MISSING")

    def test_b295_unhealthy_ledger_blocks_deployment_continuity(self):
        receipt = self._receipt()
        self._write_runtime(receipt, source="before\n", live="current\n")
        self.ledger.archive(receipt)
        self.ledger.receipt_path(receipt["receipt_digest"]).write_text(
            "{}",
            encoding="utf-8",
        )
        session = self._session(source_hash=receipt["proposed_hash"])
        result = self.gate.check_deploy(session)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "RECEIPT_LEDGER_UNHEALTHY")

    def test_b296_new_receipt_is_v2_and_links_latest_evidence(self):
        previous = self._receipt()
        self.ledger.archive(previous)
        deployment = SafeDevelopmentDeployment(
            self.root,
            ledger=self.ledger,
        )
        session = self._session(
            session_id="safe-dev-continuity0002",
            source_hash=previous["proposed_hash"],
            proposed_hash="d" * 64,
            deployment={"backup_hash": "e" * 64},
        )
        receipt = deployment._build_receipt(
            session,
            operation="DEPLOY",
            outcome="DEPLOYED",
            completed_at="2026-08-01T22:00:00+00:00",
        )
        self.assertEqual(receipt["schema_version"], 2)
        self.assertEqual(
            receipt["previous_receipt_digest"],
            previous["receipt_digest"],
        )
        self.assertTrue(SafeDevelopmentDeployment.verify_receipt(receipt))

    def test_b296_rollback_links_session_deploy_before_backfill_archive(self):
        deployment_receipt = self._receipt(schema_version=2)
        session = self._session(
            status="DEPLOYED",
            deployment={
                "backup_hash": deployment_receipt["backup_hash"],
                "receipt": deployment_receipt,
            },
        )
        deployment = SafeDevelopmentDeployment(
            self.root,
            ledger=self.ledger,
        )
        rollback = deployment._build_receipt(
            session,
            operation="ROLLBACK",
            outcome="ROLLED_BACK",
            completed_at="2026-08-01T22:00:00+00:00",
        )
        self.assertEqual(
            rollback["previous_receipt_digest"],
            deployment_receipt["receipt_digest"],
        )

    def test_b296_first_v2_receipt_can_start_a_chain(self):
        receipt = self._receipt(schema_version=2)
        archived = self.ledger.archive(receipt)
        self.assertTrue(archived["success"])
        self.assertTrue(self.ledger.audit()["success"])

    def test_b297_sequential_v2_chain_is_indexed_and_valid(self):
        first = self._receipt()
        second = self._receipt(
            session_id="safe-dev-continuity0002",
            completed_at="2026-08-01T22:00:00+00:00",
            schema_version=2,
            previous_receipt_digest=first["receipt_digest"],
        )
        self.ledger.archive(first)
        self.ledger.archive(second)
        audit = self.ledger.audit()
        self.assertTrue(audit["success"], audit)
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["schema_version"], 4)
        self.assertEqual(
            index["receipts"][second["receipt_digest"]][
                "previous_receipt_digest"
            ],
            first["receipt_digest"],
        )

    def test_b297_missing_previous_receipt_is_rejected_prewrite(self):
        receipt = self._receipt(
            schema_version=2,
            previous_receipt_digest="d" * 64,
        )
        with self.assertRaisesRegex(ValueError, "PREVIOUS_RECEIPT_MISSING"):
            self.ledger.archive(receipt)
        self.assertFalse(
            self.ledger.receipt_path(receipt["receipt_digest"]).exists()
        )

    def test_b297_chain_must_point_to_immediate_predecessor(self):
        first = self._receipt(
            completed_at="2026-08-01T20:00:00+00:00",
        )
        middle = self._receipt(
            session_id="safe-dev-continuity0002",
            completed_at="2026-08-01T21:00:00+00:00",
        )
        latest = self._receipt(
            session_id="safe-dev-continuity0003",
            completed_at="2026-08-01T22:00:00+00:00",
            schema_version=2,
            previous_receipt_digest=first["receipt_digest"],
        )
        self.ledger.archive(first)
        self.ledger.archive(middle)
        with self.assertRaisesRegex(
            ValueError,
            "RECEIPT_CHAIN_PREDECESSOR_MISMATCH",
        ):
            self.ledger.archive(latest)

    def test_b297_chain_time_must_move_forward(self):
        future = self._receipt(
            completed_at="2026-08-01T22:00:00+00:00",
        )
        past = self._receipt(
            session_id="safe-dev-continuity0002",
            completed_at="2026-08-01T21:00:00+00:00",
            schema_version=2,
            previous_receipt_digest=future["receipt_digest"],
        )
        self.ledger.archive(future)
        with self.assertRaisesRegex(
            ValueError,
            "NON_MONOTONIC_RECEIPT_CHAIN",
        ):
            self.ledger.archive(past)

    def test_b297_late_legacy_backfill_is_visible_but_not_destructive(self):
        current = self._receipt(
            session_id="safe-dev-continuity0002",
            completed_at="2026-08-01T22:00:00+00:00",
            schema_version=2,
        )
        older = self._receipt(
            completed_at="2026-08-01T21:00:00+00:00",
        )
        self.ledger.archive(current)
        self.ledger.archive(older)
        audit = self.ledger.audit()
        self.assertTrue(audit["success"], audit)
        self.assertIn(
            "RECEIPT_CHAIN_BOOTSTRAP_AFTER_HISTORY",
            {item["code"] for item in audit["timeline_warnings"]},
        )

    def test_b298_rollback_requires_its_deployment_to_be_latest(self):
        deployment = self._receipt()
        self._write_runtime(
            deployment,
            source="before\n",
            live="deployed\n",
        )
        self.ledger.archive(deployment)
        session = self._session(
            source_hash=deployment["source_hash"],
            proposed_hash=deployment["proposed_hash"],
            status="DEPLOYED",
            deployment={"receipt": deployment},
        )
        result = self.gate.check_rollback(session)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["status"], "ROLLBACK_CONTINUITY_VERIFIED")

    def test_b298_superseded_deployment_cannot_roll_back_newer_history(self):
        deployment = self._receipt()
        newer = self._receipt(
            session_id="safe-dev-continuity0002",
            completed_at="2026-08-01T22:00:00+00:00",
            schema_version=2,
            previous_receipt_digest=deployment["receipt_digest"],
        )
        self.ledger.archive(deployment)
        self.ledger.archive(newer)
        session = self._session(
            status="DEPLOYED",
            deployment={"receipt": deployment},
        )
        result = self.gate.check_rollback(session)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "ROLLBACK_SUPERSEDED")

    def test_b299_blocked_deploy_writes_neither_target_nor_backup(self):
        target = self.root / "app/integration.py"
        target.write_text("value = 1\n", encoding="utf-8")
        store = SafeDevelopmentStore(self.root)
        session = store.new_session(
            target="app/integration.py",
            transform="test_transform",
            title="Blocked integration",
            rationale="Continuity must block before workspace access.",
            risk_score=5.0,
            confidence=0.99,
        )
        session.status = "READY_FOR_APPROVAL"
        session.source_hash = self._hash("value = 1\n")
        session.proposed_hash = self._hash("value = 2\n")
        session.fingerprint = "approved-fingerprint"
        store.save_session(session)
        deployment = SafeDevelopmentDeployment(
            self.root,
            store=store,
            continuity=_BlockedContinuity(),
        )
        result = deployment.deploy(
            session.session_id,
            session.fingerprint,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "DEPLOYMENT_CONTINUITY_BLOCKED")
        self.assertEqual(
            target.read_text(encoding="utf-8"),
            "value = 1\n",
        )
        self.assertFalse(
            (
                store.backups_root
                / session.session_id
                / "original.py"
            ).exists()
        )

    def test_b300_config_freezes_continuity_contract(self):
        project = Path(__file__).resolve().parents[1]
        config = json.loads(
            (
                project
                / "config/b291_b300_autonomous_development_3_7.json"
            ).read_text(encoding="utf-8")
        )
        safety = config["safety"]
        self.assertTrue(safety["deployment_continuity_gate"])
        self.assertTrue(safety["no_history_bootstrap_allowed"])
        self.assertTrue(safety["v2_receipts_require_previous_digest_field"])
        self.assertTrue(safety["receipt_chain_conflicts_fail_closed"])
        self.assertTrue(safety["rollback_supersession_blocked"])
        self.assertFalse(safety["automatic_approval"])
        self.assertFalse(safety["automatic_deployment"])


if __name__ == "__main__":
    unittest.main()

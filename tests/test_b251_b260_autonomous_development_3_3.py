from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.ai.software_engineer.deployment_receipt_ledger import (
    DeploymentReceiptLedger,
)
from app.ai.software_engineer.safe_development_deployment import (
    SafeDevelopmentDeployment,
)
from app.ai.software_engineer.safe_development_models import SafeDevelopmentPolicy
from app.ai.software_engineer.safe_development_store import SafeDevelopmentStore


class B251B260AutonomousDevelopment33Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ledger = DeploymentReceiptLedger(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def _receipt(
        self,
        *,
        session_id="safe-dev-ledger0001",
        campaign_id="autodev-work-ledger0001",
        operation="DEPLOY",
        target="app/demo.py",
        extra=None,
    ):
        receipt = {
            "schema_version": 1,
            "operation": operation,
            "outcome": "DEPLOYED" if operation == "DEPLOY" else "ROLLED_BACK",
            "session_id": session_id,
            "campaign_id": campaign_id,
            "work_item_id": "work-item-ledger0001",
            "target": target,
            "source_hash": "a" * 64,
            "proposed_hash": "b" * 64,
            "backup_hash": "c" * 64,
            "completed_at": "2026-08-01T20:00:00+00:00",
            "validation_success": True,
            "test_count": 7,
            "verified": True,
            "automatic_approval": False,
            "automatic_deployment": False,
        }
        receipt.update(dict(extra or {}))
        receipt["receipt_digest"] = SafeDevelopmentDeployment._receipt_digest(
            receipt
        )
        return receipt

    def test_b251_archives_receipt_outside_session_directory(self):
        receipt = self._receipt()
        result = self.ledger.archive(receipt)
        path = self.ledger.receipt_path(receipt["receipt_digest"])
        self.assertTrue(result["created"])
        self.assertTrue(path.is_file())
        self.assertNotIn("sessions", path.parts)
        self.assertTrue(self.ledger.verify(receipt["receipt_digest"])["success"])

    def test_b252_atomic_index_contains_bounded_public_summary(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        record = index["receipts"][receipt["receipt_digest"]]
        self.assertEqual(record["session_id"], receipt["session_id"])
        self.assertEqual(record["campaign_id"], receipt["campaign_id"])
        self.assertEqual(record["target"], "app/demo.py")
        self.assertNotIn("source_hash", record)
        self.assertNotIn("backup_hash", record)

    def test_b253_archiving_same_receipt_is_idempotent(self):
        receipt = self._receipt()
        first = self.ledger.archive(receipt)
        second = self.ledger.archive(receipt)
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(index["order"], [receipt["receipt_digest"]])

    def test_b254_tampered_receipt_is_detected(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        path = self.ledger.receipt_path(receipt["receipt_digest"])
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["receipt"]["target"] = "app/tampered.py"
        path.write_text(json.dumps(artifact), encoding="utf-8")
        result = self.ledger.verify(receipt["receipt_digest"])
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "RECEIPT_ARCHIVE_TAMPERED")

    def test_b254_tampered_archive_metadata_is_detected(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        path = self.ledger.receipt_path(receipt["receipt_digest"])
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["archived_at"] = "2099-01-01T00:00:00+00:00"
        path.write_text(json.dumps(artifact), encoding="utf-8")
        self.assertFalse(self.ledger.verify(receipt["receipt_digest"])["success"])

    def test_b255_queries_filter_by_campaign_and_session(self):
        first = self._receipt()
        second = self._receipt(
            session_id="safe-dev-ledger0002",
            campaign_id="autodev-work-ledger0002",
            target="app/second.py",
        )
        self.ledger.archive(first)
        self.ledger.archive(second)
        by_campaign = self.ledger.list_receipts(
            campaign_id=first["campaign_id"]
        )
        by_session = self.ledger.list_receipts(
            session_id=second["session_id"]
        )
        self.assertEqual([item["receipt_digest"] for item in by_campaign], [
            first["receipt_digest"],
        ])
        self.assertEqual([item["receipt_digest"] for item in by_session], [
            second["receipt_digest"],
        ])
        self.assertTrue(by_campaign[0]["verified"])

    def test_b256_rejects_secret_fields_even_with_valid_digest(self):
        receipt = self._receipt(extra={"access_token": "secret-value"})
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)

    def test_b256_rejects_absolute_target_even_with_valid_digest(self):
        receipt = self._receipt(target=str(self.root / "app/demo.py"))
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)

    def test_b256_rejects_empty_target_even_with_valid_digest(self):
        receipt = self._receipt(target="")
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)

    def test_b257_invalid_digest_never_escapes_receipt_root(self):
        result = self.ledger.verify("../../session.json")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "INVALID_RECEIPT_DIGEST")

    def test_b258_deployed_session_is_never_pruned(self):
        store = SafeDevelopmentStore(
            self.root,
            policy=SafeDevelopmentPolicy(max_sessions=1),
        )
        deployed = store.new_session(
            target="app/a.py",
            transform="none",
            title="deployed",
            rationale="test",
            risk_score=1,
            confidence=1,
        )
        deployed.status = "DEPLOYED"
        store.save_session(deployed)
        newer = store.new_session(
            target="app/b.py",
            transform="none",
            title="newer",
            rationale="test",
            risk_score=1,
            confidence=1,
        )
        newer.status = "DISCARDED"
        store.save_session(newer)
        self.assertEqual(store.load_session(deployed.session_id).status, "DEPLOYED")

    def test_b259_rolled_back_without_archive_is_protected_from_pruning(self):
        store = SafeDevelopmentStore(
            self.root,
            policy=SafeDevelopmentPolicy(max_sessions=1),
        )
        rolled_back = store.new_session(
            target="app/a.py",
            transform="none",
            title="rolled back",
            rationale="test",
            risk_score=1,
            confidence=1,
        )
        rolled_back.status = "ROLLED_BACK"
        store.save_session(rolled_back)
        store.new_session(
            target="app/b.py",
            transform="none",
            title="newer",
            rationale="test",
            risk_score=1,
            confidence=1,
        )
        self.assertEqual(
            store.load_session(rolled_back.session_id).status,
            "ROLLED_BACK",
        )

    def test_b259_archived_rolled_back_session_can_be_pruned(self):
        store = SafeDevelopmentStore(
            self.root,
            policy=SafeDevelopmentPolicy(max_sessions=1),
        )
        rolled_back = store.new_session(
            target="app/a.py",
            transform="none",
            title="rolled back",
            rationale="test",
            risk_score=1,
            confidence=1,
        )
        receipt = self._receipt(
            session_id=rolled_back.session_id,
            campaign_id="",
            operation="ROLLBACK",
        )
        self.ledger.archive(receipt)
        rolled_back.status = "ROLLED_BACK"
        rolled_back.rollback = {"verified": True, "receipt": receipt}
        store.save_session(rolled_back)
        store.new_session(
            target="app/b.py",
            transform="none",
            title="newer",
            rationale="test",
            risk_score=1,
            confidence=1,
        )
        with self.assertRaises(FileNotFoundError):
            store.load_session(rolled_back.session_id)
        self.assertTrue(self.ledger.verify(receipt["receipt_digest"])["success"])

    def test_b260_config_freezes_ledger_and_retention_contract(self):
        project = Path(__file__).resolve().parents[1]
        config = json.loads(
            (project / "config/b251_b260_autonomous_development_3_3.json")
            .read_text(encoding="utf-8")
        )
        safety = config["safety"]
        self.assertTrue(safety["append_only_receipt_archive"])
        self.assertTrue(safety["protect_deployed_sessions_from_pruning"])
        self.assertTrue(safety["prune_rolled_back_only_after_receipt_archive"])
        self.assertFalse(safety["automatic_approval"])
        self.assertFalse(safety["automatic_deployment"])


if __name__ == "__main__":
    unittest.main()

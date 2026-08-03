from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from app.ai.software_engineer.deployment_receipt_attestation import (
    DeploymentReceiptAttestation,
)
from app.ai.software_engineer.deployment_receipt_ledger import (
    DeploymentReceiptLedger,
)
from app.ai.software_engineer.safe_development_deployment import (
    SafeDevelopmentDeployment,
)


class B281B290AutonomousDevelopment36Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ledger = DeploymentReceiptLedger(self.root)
        self.attestation = DeploymentReceiptAttestation(
            self.root,
            ledger=self.ledger,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _receipt(
        self,
        *,
        session_id="safe-dev-timeline0001",
        campaign_id="autodev-work-timeline0001",
        work_item_id="work-item-timeline0001",
        target="app/timeline.py",
        operation="DEPLOY",
        completed_at="2026-08-01T22:00:00+00:00",
        source_hash=None,
        proposed_hash=None,
        backup_hash=None,
    ):
        receipt = {
            "schema_version": 1,
            "operation": operation,
            "outcome": "DEPLOYED" if operation == "DEPLOY" else "ROLLED_BACK",
            "session_id": session_id,
            "campaign_id": campaign_id,
            "work_item_id": work_item_id,
            "target": target,
            "source_hash": source_hash or "a" * 64,
            "proposed_hash": proposed_hash or "b" * 64,
            "backup_hash": backup_hash or "c" * 64,
            "completed_at": completed_at,
            "validation_success": True,
            "test_count": 19,
            "verified": True,
            "automatic_approval": False,
            "automatic_deployment": False,
        }
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
        receipt["source_hash"] = hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest()
        receipt["backup_hash"] = hashlib.sha256(
            backup.read_bytes()
        ).hexdigest()
        receipt["proposed_hash"] = hashlib.sha256(
            live.encode("utf-8")
        ).hexdigest()
        receipt["receipt_digest"] = SafeDevelopmentDeployment._receipt_digest(
            receipt
        )
        return target, backup

    def test_b281_completed_at_order_wins_over_archive_order(self):
        newer = self._receipt(
            session_id="safe-dev-timeline0002",
            completed_at="2026-08-01T23:00:00+00:00",
        )
        older = self._receipt(
            completed_at="2026-08-01T21:00:00+00:00",
        )
        self.ledger.archive(newer)
        self.ledger.archive(older)
        records = self.ledger.list_receipts()
        self.assertEqual(
            [item["receipt_digest"] for item in records],
            [newer["receipt_digest"], older["receipt_digest"]],
        )

    def test_b282_timezone_offsets_are_normalized_for_ordering(self):
        earlier = self._receipt(
            completed_at="2026-08-01T23:30:00+02:00",
        )
        later = self._receipt(
            session_id="safe-dev-timeline0002",
            completed_at="2026-08-01T22:00:00+00:00",
        )
        self.ledger.archive(earlier)
        self.ledger.archive(later)
        self.assertEqual(
            self.ledger.list_receipts()[0]["receipt_digest"],
            later["receipt_digest"],
        )

    def test_b283_late_backfill_does_not_supersede_live_attestation(self):
        newer = self._receipt(
            session_id="safe-dev-timeline0002",
            campaign_id="autodev-work-timeline0002",
            work_item_id="work-item-timeline0002",
            completed_at="2026-08-01T23:00:00+00:00",
        )
        self._write_runtime(newer, source="new base\n", live="new live\n")
        self.ledger.archive(newer)
        older = self._receipt(
            completed_at="2026-08-01T21:00:00+00:00",
        )
        self.ledger.archive(older)
        result = self.attestation.attest_target("app/timeline.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["receipt_digest"], newer["receipt_digest"])

    def test_b284_duplicate_deploy_for_session_is_rejected_prewrite(self):
        first = self._receipt()
        second = self._receipt(
            completed_at="2026-08-01T22:01:00+00:00",
        )
        self.ledger.archive(first)
        with self.assertRaises(ValueError):
            self.ledger.archive(second)
        self.assertFalse(
            self.ledger.receipt_path(second["receipt_digest"]).exists()
        )

    def test_b285_duplicate_rollback_for_session_is_rejected(self):
        first = self._receipt(
            operation="AUTOMATIC_ROLLBACK",
        )
        second = self._receipt(
            operation="ROLLBACK",
            completed_at="2026-08-01T22:01:00+00:00",
        )
        self.ledger.archive(first)
        with self.assertRaises(ValueError):
            self.ledger.archive(second)

    def test_b285_orphan_automatic_rollback_is_warning_not_failure(self):
        receipt = self._receipt(operation="AUTOMATIC_ROLLBACK")
        self.ledger.archive(receipt)
        audit = self.ledger.audit()
        self.assertTrue(audit["success"])
        self.assertEqual(audit["timeline_conflicts"], [])
        self.assertEqual(
            audit["timeline_warnings"][0]["code"],
            "ORPHAN_ROLLBACK_RECEIPT",
        )

    def test_b286_rollback_cannot_precede_deployment(self):
        deployment = self._receipt(
            completed_at="2026-08-01T22:00:00+00:00",
        )
        rollback = self._receipt(
            operation="ROLLBACK",
            completed_at="2026-08-01T21:00:00+00:00",
        )
        self.ledger.archive(deployment)
        with self.assertRaises(ValueError):
            self.ledger.archive(rollback)

    def test_b287_rollback_hashes_must_match_deployment(self):
        deployment = self._receipt()
        rollback = self._receipt(
            operation="ROLLBACK",
            completed_at="2026-08-01T22:01:00+00:00",
            proposed_hash="d" * 64,
        )
        self.ledger.archive(deployment)
        with self.assertRaises(ValueError):
            self.ledger.archive(rollback)

    def test_b287_session_target_cannot_change_during_rollback(self):
        deployment = self._receipt()
        rollback = self._receipt(
            operation="ROLLBACK",
            target="app/other.py",
            completed_at="2026-08-01T22:01:00+00:00",
        )
        self.ledger.archive(deployment)
        with self.assertRaises(ValueError):
            self.ledger.archive(rollback)

    def test_b288_valid_deploy_then_rollback_has_clean_timeline(self):
        deployment = self._receipt()
        rollback = self._receipt(
            operation="ROLLBACK",
            completed_at="2026-08-01T22:01:00+00:00",
        )
        self.ledger.archive(deployment)
        self.ledger.archive(rollback)
        audit = self.ledger.audit()
        self.assertTrue(audit["success"])
        self.assertEqual(audit["timeline_conflicts"], [])
        self.assertEqual(
            self.ledger.list_receipts()[0]["receipt_digest"],
            rollback["receipt_digest"],
        )

    def test_b288_audit_detects_preexisting_timeline_conflict(self):
        first = self._receipt()
        second = self._receipt(
            completed_at="2026-08-01T22:01:00+00:00",
        )
        self.ledger.archive(first)
        artifact = {
            "schema_version": 1,
            "archived_at": "2026-08-01T22:02:00+00:00",
            "receipt": second,
        }
        artifact["archive_digest"] = self.ledger._artifact_digest(artifact)
        path = self.ledger.receipt_path(second["receipt_digest"])
        path.write_text(json.dumps(artifact), encoding="utf-8")
        audit = self.ledger.audit(repair_index=True)
        self.assertFalse(audit["success"])
        self.assertEqual(
            audit["status"],
            "RECEIPT_LEDGER_TIMELINE_CONFLICT",
        )
        self.assertEqual(
            audit["timeline_conflicts"][0]["code"],
            "DUPLICATE_DEPLOY_RECEIPT",
        )

    def test_b289_version_two_index_is_migrated_to_timeline_index(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        index["schema_version"] = 2
        index["index_digest"] = self.ledger._index_digest(index)
        self.ledger.index_path.write_text(json.dumps(index), encoding="utf-8")
        result = self.ledger.audit(repair_index=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["index_repaired"])
        upgraded = json.loads(
            self.ledger.index_path.read_text(encoding="utf-8")
        )
        self.assertEqual(upgraded["schema_version"], 4)

    def test_b290_config_freezes_semantic_timeline_contract(self):
        project = Path(__file__).resolve().parents[1]
        config = json.loads(
            (project / "config/b281_b290_autonomous_development_3_6.json")
            .read_text(encoding="utf-8")
        )
        safety = config["safety"]
        self.assertTrue(safety["completed_at_defines_latest_state"])
        self.assertTrue(safety["rollback_requires_matching_deployment_evidence"])
        self.assertTrue(safety["timeline_conflicts_fail_closed"])
        self.assertTrue(safety["late_backfill_never_supersedes_newer_state"])
        self.assertFalse(safety["automatic_approval"])
        self.assertFalse(safety["automatic_deployment"])


if __name__ == "__main__":
    unittest.main()

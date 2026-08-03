from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from app.ai.software_engineer.deployment_receipt_ledger import (
    DeploymentReceiptLedger,
)
from app.ai.software_engineer.safe_autonomous_development_service import (
    SafeAutonomousDevelopmentService,
)
from app.ai.software_engineer.safe_development_deployment import (
    SafeDevelopmentDeployment,
)
from app.ai.software_engineer.safe_development_models import SafeDevelopmentPolicy


class B261B270AutonomousDevelopment34Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ledger = DeploymentReceiptLedger(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def _receipt(
        self,
        *,
        session_id="safe-dev-recovery0001",
        campaign_id="autodev-work-recovery0001",
        target="app/recovery.py",
        completed_at="2026-08-01T21:00:00+00:00",
    ):
        receipt = {
            "schema_version": 1,
            "operation": "DEPLOY",
            "outcome": "DEPLOYED",
            "session_id": session_id,
            "campaign_id": campaign_id,
            "work_item_id": "work-item-recovery0001",
            "target": target,
            "source_hash": "a" * 64,
            "proposed_hash": "b" * 64,
            "backup_hash": "c" * 64,
            "completed_at": completed_at,
            "validation_success": True,
            "test_count": 11,
            "verified": True,
            "automatic_approval": False,
            "automatic_deployment": False,
        }
        receipt["receipt_digest"] = SafeDevelopmentDeployment._receipt_digest(
            receipt
        )
        return receipt

    def test_b261_index_has_verified_integrity_digest(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["schema_version"], 4)
        self.assertTrue(index["index_digest"])
        self.assertTrue(self.ledger._index_is_valid(index))

    def test_b262_inventory_audit_reports_clean_ledger(self):
        self.ledger.archive(self._receipt())
        audit = self.ledger.audit()
        self.assertTrue(audit["success"])
        self.assertEqual(audit["status"], "RECEIPT_LEDGER_CURRENT")
        self.assertEqual(audit["valid_receipts"], 1)
        self.assertFalse(audit["repair_required"])

    def test_b263_rebuild_restores_deleted_index(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        self.ledger.index_path.unlink()
        result = self.ledger.rebuild_index()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "RECEIPT_INDEX_REBUILT")
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["order"], [receipt["receipt_digest"]])
        self.assertTrue(self.ledger._index_is_valid(index))

    def test_b264_list_auto_recovers_corrupt_index(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        self.ledger.index_path.write_text("{broken", encoding="utf-8")
        records = self.ledger.list_receipts()
        self.assertEqual(
            [item["receipt_digest"] for item in records],
            [receipt["receipt_digest"]],
        )
        self.assertTrue(self.ledger.audit()["success"])

    def test_b264_malformed_index_types_are_repaired_without_crash(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        self.ledger.index_path.write_text(
            json.dumps({
                "schema_version": 2,
                "receipts": [],
                "order": [{}],
                "index_digest": "x",
            }),
            encoding="utf-8",
        )
        result = self.ledger.audit(repair_index=True)
        self.assertTrue(result["success"])
        self.assertTrue(result["index_repaired"])

    def test_b265_tampered_index_record_is_detected_and_rebuilt(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        index["receipts"][receipt["receipt_digest"]]["target"] = "app/fake.py"
        index["index_digest"] = self.ledger._index_digest(index)
        self.ledger.index_path.write_text(json.dumps(index), encoding="utf-8")
        detected = self.ledger.audit()
        self.assertFalse(detected["success"])
        self.assertEqual(
            detected["mismatched_index_entries"],
            [receipt["receipt_digest"]],
        )
        repaired = self.ledger.audit(repair_index=True)
        self.assertTrue(repaired["success"])
        self.assertTrue(repaired["index_repaired"])

    def test_b266_live_writer_lock_fails_closed(self):
        ledger = DeploymentReceiptLedger(
            self.root,
            lock_timeout_seconds=0.02,
            lock_poll_seconds=0.002,
        )
        ledger.write_lock_path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        ledger.write_lock_path.write_text(
            json.dumps({
                "token": "live-owner",
                "pid": 123,
                "acquired_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=1)).isoformat(),
            }),
            encoding="utf-8",
        )
        with self.assertRaises(TimeoutError):
            ledger.archive(self._receipt())
        self.assertTrue(ledger.write_lock_path.exists())

    def test_b267_expired_writer_lock_is_recovered(self):
        self.ledger.write_lock_path.parent.mkdir(parents=True, exist_ok=True)
        expired = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.ledger.write_lock_path.write_text(
            json.dumps({
                "token": "dead-owner",
                "pid": 123,
                "acquired_at": expired.isoformat(),
                "expires_at": expired.isoformat(),
            }),
            encoding="utf-8",
        )
        result = self.ledger.archive(self._receipt())
        self.assertTrue(result["success"])
        self.assertFalse(self.ledger.write_lock_path.exists())

    def test_b268_concurrent_archives_preserve_every_receipt(self):
        first = self._receipt(
            session_id="safe-dev-recovery0001",
            target="app/first.py",
            completed_at="2026-08-01T21:00:00+00:00",
        )
        second = self._receipt(
            session_id="safe-dev-recovery0002",
            target="app/second.py",
            completed_at="2026-08-01T21:00:01+00:00",
        )
        ledgers = [
            DeploymentReceiptLedger(self.root),
            DeploymentReceiptLedger(self.root),
        ]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda pair: pair[0].archive(pair[1]),
                zip(ledgers, [first, second]),
            ))
        self.assertTrue(all(item["success"] for item in results))
        records = self.ledger.list_receipts()
        self.assertEqual(
            {item["receipt_digest"] for item in records},
            {first["receipt_digest"], second["receipt_digest"]},
        )
        self.assertTrue(self.ledger.audit()["success"])

    def test_b269_invalid_archive_is_excluded_and_reported(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        path = self.ledger.receipt_path(receipt["receipt_digest"])
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["receipt"]["target"] = "app/tampered.py"
        path.write_text(json.dumps(artifact), encoding="utf-8")
        result = self.ledger.audit(repair_index=True)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "RECEIPT_LEDGER_TAMPERED")
        self.assertEqual(result["valid_receipts"], 0)
        self.assertEqual(len(result["invalid_artifacts"]), 1)
        self.assertFalse(result["index_repaired"])
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["order"], [receipt["receipt_digest"]])

    def test_b269_deleted_archive_is_not_silently_removed_from_index(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        self.ledger.receipt_path(receipt["receipt_digest"]).unlink()
        result = self.ledger.audit(repair_index=True)
        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "RECEIPT_LEDGER_EVIDENCE_MISSING",
        )
        self.assertEqual(
            result["missing_artifacts"],
            [receipt["receipt_digest"]],
        )
        self.assertFalse(result["index_repaired"])
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["order"], [receipt["receipt_digest"]])

    def test_b269_rehashed_secret_field_still_fails_semantic_validation(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        path = self.ledger.receipt_path(receipt["receipt_digest"])
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["receipt"]["access_token"] = "not-allowed"
        artifact["receipt"]["receipt_digest"] = self.ledger._receipt_digest(
            artifact["receipt"]
        )
        artifact["archive_digest"] = self.ledger._artifact_digest(artifact)
        path.write_text(json.dumps(artifact), encoding="utf-8")
        result = self.ledger.verify(receipt["receipt_digest"])
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "RECEIPT_ARCHIVE_TAMPERED")

    def test_b269_service_exposes_repair_and_fails_closed(self):
        service = SafeAutonomousDevelopmentService(
            self.root,
            policy=SafeDevelopmentPolicy(),
        )
        service.deployment.ledger.archive(self._receipt())
        service.deployment.ledger.index_path.unlink()
        repaired = service.audit_receipt_ledger(repair_index=True)
        self.assertTrue(repaired["success"])
        self.assertTrue(repaired["index_repaired"])

        service.deployment.ensure_receipts = lambda session_id: {
            "success": True,
            "status": "RECEIPTS_CURRENT",
            "session_id": session_id,
        }
        service.audit_receipt_ledger = lambda repair_index=False: {
            "success": False,
            "status": "RECEIPT_LEDGER_TAMPERED",
        }
        result = service.ensure_receipts("safe-dev-recovery0001")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "RECEIPT_LEDGER_INTEGRITY_FAILED")

    def test_b270_legacy_index_is_upgraded_idempotently(self):
        receipt = self._receipt()
        self.ledger.archive(receipt)
        index = json.loads(self.ledger.index_path.read_text(encoding="utf-8"))
        index["schema_version"] = 1
        index.pop("index_digest")
        self.ledger.index_path.write_text(json.dumps(index), encoding="utf-8")
        result = self.ledger.archive(receipt)
        self.assertFalse(result["created"])
        upgraded = json.loads(
            self.ledger.index_path.read_text(encoding="utf-8")
        )
        self.assertEqual(upgraded["schema_version"], 4)
        self.assertTrue(self.ledger._index_is_valid(upgraded))

    def test_b270_config_freezes_recovery_and_concurrency_contract(self):
        project = Path(__file__).resolve().parents[1]
        config = json.loads(
            (project / "config/b261_b270_autonomous_development_3_4.json")
            .read_text(encoding="utf-8")
        )
        safety = config["safety"]
        self.assertTrue(safety["verified_index_digest"])
        self.assertTrue(safety["automatic_index_recovery"])
        self.assertTrue(safety["cross_process_writer_lock"])
        self.assertTrue(safety["invalid_artifacts_fail_closed"])
        self.assertTrue(safety["missing_artifacts_fail_closed"])
        self.assertFalse(safety["automatic_approval"])
        self.assertFalse(safety["automatic_deployment"])


if __name__ == "__main__":
    unittest.main()

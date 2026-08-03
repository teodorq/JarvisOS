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
from app.ai.software_engineer.safe_autonomous_development_service import (
    SafeAutonomousDevelopmentService,
)
from app.ai.software_engineer.safe_development_deployment import (
    SafeDevelopmentDeployment,
)
from app.ai.software_engineer.safe_development_models import SafeDevelopmentPolicy


class B271B280AutonomousDevelopment35Tests(unittest.TestCase):
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

    @staticmethod
    def _text_hash(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _bytes_hash(value):
        return hashlib.sha256(value).hexdigest()

    def _state(
        self,
        *,
        session_id="safe-dev-attest0001",
        campaign_id="autodev-work-attest0001",
        work_item_id="work-item-attest0001",
        target="app/attested.py",
        source="before\n",
        proposed="after\n",
        operation="DEPLOY",
        completed_at="2026-08-01T22:00:00+00:00",
        archive=True,
    ):
        target_path = self.root / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        live = proposed if operation == "DEPLOY" else source
        target_path.write_text(live, encoding="utf-8")
        backup = (
            self.root
            / "data/autodev/safe_development_2/backups"
            / session_id
            / "original.py"
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(source, encoding="utf-8")
        receipt = {
            "schema_version": 1,
            "operation": operation,
            "outcome": "DEPLOYED" if operation == "DEPLOY" else "ROLLED_BACK",
            "session_id": session_id,
            "campaign_id": campaign_id,
            "work_item_id": work_item_id,
            "target": target,
            "source_hash": self._text_hash(source),
            "proposed_hash": self._text_hash(proposed),
            "backup_hash": self._bytes_hash(backup.read_bytes()),
            "completed_at": completed_at,
            "validation_success": True,
            "test_count": 17,
            "verified": True,
            "automatic_approval": False,
            "automatic_deployment": False,
        }
        receipt["receipt_digest"] = SafeDevelopmentDeployment._receipt_digest(
            receipt
        )
        if archive:
            self.ledger.archive(receipt)
        return receipt, target_path, backup

    def _redigest(self, receipt):
        receipt["receipt_digest"] = SafeDevelopmentDeployment._receipt_digest(
            receipt
        )
        return receipt

    def test_b271_rejects_unknown_operation_with_valid_digest(self):
        receipt, _, _ = self._state(archive=False)
        receipt["operation"] = "ERASE"
        self._redigest(receipt)
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)

    def test_b271_rejects_invalid_hash_and_missing_required_field(self):
        receipt, _, _ = self._state(archive=False)
        receipt["source_hash"] = "short"
        self._redigest(receipt)
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)
        receipt, _, _ = self._state(archive=False)
        receipt.pop("backup_hash")
        self._redigest(receipt)
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)

    def test_b271_rejects_naive_timestamp_and_invalid_boolean(self):
        receipt, _, _ = self._state(archive=False)
        receipt["completed_at"] = "2026-08-01T22:00:00"
        self._redigest(receipt)
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)
        receipt, _, _ = self._state(archive=False)
        receipt["verified"] = 1
        self._redigest(receipt)
        with self.assertRaises(ValueError):
            self.ledger.archive(receipt)

    def test_b272_selects_latest_receipt_for_target(self):
        first, _, _ = self._state()
        second, target, _ = self._state(
            operation="ROLLBACK",
            completed_at="2026-08-01T22:01:00+00:00",
        )
        result = self.attestation.attest_target("app/attested.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ROLLBACK")
        self.assertEqual(result["receipt_digest"], second["receipt_digest"])
        self.assertNotEqual(first["receipt_digest"], second["receipt_digest"])
        self.assertEqual(
            self._text_hash(target.read_text(encoding="utf-8")),
            second["source_hash"],
        )

    def test_b273_attests_live_deployed_target(self):
        receipt, _, _ = self._state()
        result = self.attestation.attest_target(receipt["target"])
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "DEPLOYMENT_ATTESTED")
        self.assertTrue(result["live_matches"])
        self.assertTrue(result["backup_matches"])

    def test_b274_detects_live_target_drift(self):
        receipt, target, _ = self._state()
        target.write_text("manual drift\n", encoding="utf-8")
        result = self.attestation.attest_receipt(
            receipt["receipt_digest"]
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "LIVE_TARGET_DRIFT")
        self.assertFalse(result["live_matches"])

    def test_b275_detects_missing_backup(self):
        receipt, _, backup = self._state()
        backup.unlink()
        result = self.attestation.attest_receipt(
            receipt["receipt_digest"]
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "BACKUP_MISSING")

    def test_b275_detects_tampered_backup(self):
        receipt, _, backup = self._state()
        backup.write_text("tampered\n", encoding="utf-8")
        result = self.attestation.attest_receipt(
            receipt["receipt_digest"]
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "BACKUP_TAMPERED")
        self.assertFalse(result["backup_matches"])

    def test_b276_rollback_attests_restored_source_hash(self):
        receipt, _, _ = self._state(operation="ROLLBACK")
        result = self.attestation.attest_receipt(
            receipt["receipt_digest"]
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ROLLBACK")
        self.assertEqual(
            result["expected_live_hash"],
            receipt["source_hash"],
        )

    def test_b277_campaign_marks_historical_receipt_superseded(self):
        first, _, _ = self._state(
            session_id="safe-dev-attest0001",
            campaign_id="autodev-work-attest0001",
            source="base\n",
            proposed="version one\n",
        )
        second, _, _ = self._state(
            session_id="safe-dev-attest0002",
            campaign_id="autodev-work-attest0002",
            work_item_id="work-item-attest0002",
            source="version one\n",
            proposed="version two\n",
            completed_at="2026-08-01T22:02:00+00:00",
        )
        result = self.attestation.attest_campaign(
            first["campaign_id"]
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["superseded_count"], 1)
        self.assertEqual(
            result["results"][0]["superseded_by"],
            second["receipt_digest"],
        )

    def test_b277_campaign_attests_current_targets(self):
        receipt, _, _ = self._state()
        result = self.attestation.attest_campaign(
            receipt["campaign_id"]
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "CAMPAIGN_ATTESTED")
        self.assertEqual(result["attested_count"], 1)

    def test_b278_project_attestation_covers_latest_target_states(self):
        self._state()
        self._state(
            session_id="safe-dev-attest0002",
            work_item_id="work-item-attest0002",
            target="app/second.py",
            source="second before\n",
            proposed="second after\n",
            completed_at="2026-08-01T22:03:00+00:00",
        )
        result = self.attestation.attest_all()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "PROJECT_DEPLOYMENTS_ATTESTED")
        self.assertEqual(result["target_count"], 2)
        self.assertEqual(result["attested_count"], 2)

    def test_b278_attestation_digest_detects_report_tampering(self):
        receipt, _, _ = self._state()
        result = self.attestation.attest_receipt(
            receipt["receipt_digest"]
        )
        self.assertTrue(DeploymentReceiptAttestation.verify_report(result))
        result["status"] = "FAKE"
        self.assertFalse(DeploymentReceiptAttestation.verify_report(result))

    def test_b279_unhealthy_ledger_blocks_live_attestation(self):
        receipt, _, _ = self._state()
        path = self.ledger.receipt_path(receipt["receipt_digest"])
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["receipt"]["target"] = "app/tampered.py"
        path.write_text(json.dumps(artifact), encoding="utf-8")
        result = self.attestation.attest_target(receipt["target"])
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "RECEIPT_LEDGER_UNHEALTHY")

    def test_b279_service_exposes_target_campaign_and_project_attestation(self):
        receipt, _, _ = self._state()
        service = SafeAutonomousDevelopmentService(
            self.root,
            policy=SafeDevelopmentPolicy(),
        )
        by_target = service.attest_deployment_target(receipt["target"])
        by_campaign = service.attest_campaign_deployments(
            receipt["campaign_id"]
        )
        project = service.attest_all_deployments()
        self.assertTrue(by_target["success"])
        self.assertTrue(by_campaign["success"])
        self.assertTrue(project["success"])

    def test_b280_config_freezes_live_attestation_contract(self):
        project = Path(__file__).resolve().parents[1]
        config = json.loads(
            (project / "config/b271_b280_autonomous_development_3_5.json")
            .read_text(encoding="utf-8")
        )
        safety = config["safety"]
        self.assertTrue(safety["strict_receipt_semantics"])
        self.assertTrue(safety["live_target_hash_attestation"])
        self.assertTrue(safety["backup_hash_attestation"])
        self.assertTrue(safety["ledger_failure_blocks_attestation"])
        self.assertFalse(safety["automatic_approval"])
        self.assertFalse(safety["automatic_deployment"])


if __name__ == "__main__":
    unittest.main()

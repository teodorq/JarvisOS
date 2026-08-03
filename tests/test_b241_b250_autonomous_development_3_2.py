from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from app.ai.software_engineer.autonomous_work_review_service import (
    AutonomousWorkReviewService,
)
from app.ai.software_engineer.autonomous_work_store import AutonomousWorkStore
from app.ai.software_engineer.safe_autonomous_development_service import (
    SafeAutonomousDevelopmentService,
)
from app.ai.software_engineer.safe_development_deployment import (
    SafeDevelopmentDeployment,
)
from app.ai.software_engineer.safe_development_models import SafeDevelopmentPolicy


class _Validator:
    def __init__(self, *, live_success=True):
        self.live_success = live_success

    @staticmethod
    def static_validate(session, *, original, proposed):
        return {"success": True, "errors": []}

    def validate_live_target(self, session):
        return {
            "success": self.live_success,
            "tests": {
                "success": self.live_success,
                "count": 3 if self.live_success else 0,
            },
            "errors": [] if self.live_success else ["controlled failure"],
        }


class B241B250AutonomousDevelopment32Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "app").mkdir(parents=True)
        self.target = self.root / "app/demo.py"
        self.original = "value = 1\n"
        self.proposed = "value = 2\n"
        self.target.write_text(self.original, encoding="utf-8")

        policy = SafeDevelopmentPolicy(
            focused_test_timeout_seconds=5,
            live_test_timeout_seconds=5,
        )
        self.service = SafeAutonomousDevelopmentService(
            self.root,
            policy=policy,
        )
        self.service.deployment.validator = _Validator()
        self.work_store = AutonomousWorkStore(self.root)
        self.campaign = self.work_store.new_campaign(requested_tasks=1)
        self.campaign.status = "READY_FOR_APPROVAL"

        self.item_id = "work-item-receipt0001"
        self.task_fingerprint = "task-receipt0001"
        self.session = self.service.store.new_session(
            target="app/demo.py",
            transform="test_transform",
            title="Receipt test patch",
            rationale="Verify deployment evidence.",
            risk_score=8.0,
            confidence=0.99,
            metadata={
                "campaign_id": self.campaign.campaign_id,
                "work_item_id": self.item_id,
                "work_task_fingerprint": self.task_fingerprint,
                "automatic_approval": False,
                "automatic_deployment": False,
            },
        )
        self._prepare_session()
        self.campaign.items.append({
            "item_id": self.item_id,
            "status": "READY_FOR_APPROVAL",
            "task": {
                "target": "app/demo.py",
                "title": self.session.title,
                "risk_score": 8.0,
                "confidence": 0.99,
            },
            "task_fingerprint": self.task_fingerprint,
            "safe_session_id": self.session.session_id,
            "session": self.session.to_dict(),
            "risk": {"accepted": True, "tests": 3},
        })
        self.campaign.prepared_tasks = 1
        self.campaign.prepared_session_ids = [self.session.session_id]
        self.work_store.save(self.campaign)

    def tearDown(self):
        self.temporary.cleanup()

    def _prepare_session(self):
        session_dir = self.service.store.session_dir(self.session.session_id)
        artifacts = session_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        original_path = artifacts / "original.py"
        proposed_path = artifacts / "proposed.py"
        diff_path = artifacts / "change.diff"
        original_path.write_text(self.original, encoding="utf-8")
        proposed_path.write_text(self.proposed, encoding="utf-8")
        diff_path.write_text("-value = 1\n+value = 2\n", encoding="utf-8")
        self.session.status = "READY_FOR_APPROVAL"
        self.session.changed_files = ["app/demo.py"]
        self.session.changed_lines = 1
        self.session.source_hash = self._hash(self.original)
        self.session.proposed_hash = self._hash(self.proposed)
        self.session.fingerprint = self.service.store.fingerprint(
            "deploy",
            self.session.session_id,
            self.session.target,
            self.session.proposed_hash,
        )
        self.session.original_artifact = str(original_path)
        self.session.proposed_artifact = str(proposed_path)
        self.session.diff_artifact = str(diff_path)
        self.session.validation = {
            "static": {"success": True},
            "workspace": {
                "success": True,
                "tests": {"success": True, "count": 3},
            },
        }
        self.service.store.save_session(self.session)

    def _deploy(self):
        return self.service.deploy(
            self.session.session_id,
            self.session.fingerprint,
        )

    def _rollback(self):
        deployed = self.service.store.load_session(self.session.session_id)
        fingerprint = self.service.deployment.rollback_fingerprint(deployed)
        return self.service.rollback(deployed.session_id, fingerprint)

    @staticmethod
    def _hash(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def test_b241_deploy_automatically_reconciles_campaign(self):
        result = self._deploy()
        persisted = self.work_store.load(self.campaign.campaign_id)
        self.assertTrue(result["success"], result)
        self.assertEqual(
            result["campaign_reconciliation"]["campaign_status"],
            "REVIEW_COMPLETED",
        )
        self.assertEqual(persisted.status, "REVIEW_COMPLETED")
        self.assertEqual(persisted.items[0]["status"], "DEPLOYED")

    def test_b242_deployment_receipt_is_complete_and_verified(self):
        result = self._deploy()
        receipt = result["session"]["deployment"]["receipt"]
        self.assertEqual(receipt["operation"], "DEPLOY")
        self.assertEqual(receipt["outcome"], "DEPLOYED")
        self.assertEqual(receipt["target"], "app/demo.py")
        self.assertEqual(receipt["test_count"], 3)
        self.assertTrue(SafeDevelopmentDeployment.verify_receipt(receipt))
        archived = self.service.deployment.ledger.verify(
            receipt["receipt_digest"]
        )
        self.assertTrue(archived["success"], archived)

    def test_b243_receipt_detects_any_tampering(self):
        receipt = self._deploy()["session"]["deployment"]["receipt"]
        tampered = dict(receipt)
        tampered["target"] = "app/other.py"
        self.assertFalse(SafeDevelopmentDeployment.verify_receipt(tampered))
        self.assertTrue(SafeDevelopmentDeployment.verify_receipt(receipt))

    def test_b243_verified_legacy_deployment_can_backfill_receipt(self):
        self.assertTrue(self._deploy()["success"])
        session = self.service.store.load_session(self.session.session_id)
        session.deployment.pop("receipt")
        self.service.store.save_session(session)
        result = self.service.ensure_receipts(session.session_id)
        receipt = result["session"]["deployment"]["receipt"]
        self.assertEqual(result["status"], "RECEIPTS_BACKFILLED")
        self.assertEqual(result["created"], ["DEPLOY"])
        self.assertTrue(SafeDevelopmentDeployment.verify_receipt(receipt))

    def test_b243_receipt_backfill_refuses_missing_backup(self):
        self.assertTrue(self._deploy()["success"])
        session = self.service.store.load_session(self.session.session_id)
        session.deployment.pop("receipt")
        self.service.store.save_session(session)
        Path(session.backup_path).unlink()
        with self.assertRaises(FileNotFoundError):
            self.service.ensure_receipts(session.session_id)

    def test_b244_rollback_automatically_reconciles_campaign(self):
        self.assertTrue(self._deploy()["success"])
        result = self._rollback()
        persisted = self.work_store.load(self.campaign.campaign_id)
        self.assertTrue(result["success"], result)
        self.assertEqual(persisted.status, "REVIEW_COMPLETED")
        self.assertEqual(persisted.items[0]["status"], "ROLLED_BACK")
        self.assertEqual(
            result["campaign_reconciliation"]["campaign_status"],
            "REVIEW_COMPLETED",
        )

    def test_b245_rollback_receipt_and_restored_source_are_verified(self):
        self.assertTrue(self._deploy()["success"])
        result = self._rollback()
        receipt = result["session"]["rollback"]["receipt"]
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)
        self.assertEqual(receipt["operation"], "ROLLBACK")
        self.assertEqual(receipt["outcome"], "ROLLED_BACK")
        self.assertTrue(SafeDevelopmentDeployment.verify_receipt(receipt))
        archived = self.service.deployment.ledger.verify(
            receipt["receipt_digest"]
        )
        self.assertTrue(archived["success"], archived)

    def test_b246_reconciliation_is_idempotent_after_terminal_operation(self):
        self.assertTrue(self._deploy()["success"])
        before = self.work_store.load(self.campaign.campaign_id)
        event_count = len(before.events)
        review = AutonomousWorkReviewService(
            self.root,
            store=self.work_store,
            safe_development=self.service,
        )
        result = review.reconcile_campaign(self.campaign.campaign_id)
        after = self.work_store.load(self.campaign.campaign_id)
        self.assertEqual(result["reconciled_changes"], 0)
        self.assertEqual(len(after.events), event_count)

    def test_b247_campaign_summary_records_terminal_outcomes(self):
        self.assertTrue(self._deploy()["success"])
        persisted = self.work_store.load(self.campaign.campaign_id)
        summary = persisted.risk_summary
        self.assertEqual(summary["deployed_patches"], 1)
        self.assertEqual(summary["resolved_patches"], 1)
        self.assertTrue(summary["campaign_review_completed"])

    def test_b247_failed_live_validation_rolls_back_and_reconciles(self):
        self.service.deployment.validator = _Validator(live_success=False)
        result = self._deploy()
        persisted_session = self.service.store.load_session(self.session.session_id)
        persisted_campaign = self.work_store.load(self.campaign.campaign_id)
        receipt = persisted_session.rollback["receipt"]
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "AUTOMATIC_ROLLBACK_COMPLETED")
        self.assertEqual(persisted_session.status, "ROLLED_BACK")
        self.assertEqual(persisted_campaign.status, "REVIEW_COMPLETED")
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)
        self.assertEqual(receipt["operation"], "AUTOMATIC_ROLLBACK")
        self.assertTrue(SafeDevelopmentDeployment.verify_receipt(receipt))

    def test_b248_receipt_excludes_workspace_paths_and_confirmation_secret(self):
        receipt = self._deploy()["session"]["deployment"]["receipt"]
        serialized = json.dumps(receipt, sort_keys=True)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("workspace", serialized.casefold())
        self.assertNotIn(self.session.fingerprint, serialized)
        self.assertFalse(receipt["automatic_approval"])
        self.assertFalse(receipt["automatic_deployment"])

    def test_b249_non_campaign_session_does_not_touch_campaign_registry(self):
        self.session.metadata = {
            "automatic_approval": False,
            "automatic_deployment": False,
        }
        self.service.store.save_session(self.session)
        result = self._deploy()
        persisted = self.work_store.load(self.campaign.campaign_id)
        self.assertTrue(result["success"], result)
        self.assertEqual(
            result["campaign_reconciliation"]["status"],
            "NOT_A_CAMPAIGN_SESSION",
        )
        self.assertEqual(persisted.status, "READY_FOR_APPROVAL")

    def test_b250_config_keeps_bulk_and_automatic_deployment_disabled(self):
        project = Path(__file__).resolve().parents[1]
        config = json.loads(
            (project / "config/b241_b250_autonomous_development_3_2.json")
            .read_text(encoding="utf-8")
        )
        safety = config["safety"]
        self.assertFalse(safety["automatic_approval"])
        self.assertFalse(safety["automatic_deployment"])
        self.assertFalse(safety["bulk_deployment_supported"])
        self.assertTrue(safety["exact_session_fingerprint_required"])
        source = (
            project
            / "app/ai/software_engineer/safe_autonomous_development_service.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("deploy_many", source)
        self.assertNotIn("bulk_deploy", source)


if __name__ == "__main__":
    unittest.main()

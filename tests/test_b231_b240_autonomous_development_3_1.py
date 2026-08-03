from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from app.ai.software_engineer.autonomous_work_commands import (
    plan_autonomous_work_command,
)
from app.ai.software_engineer.autonomous_work_review_service import (
    AutonomousWorkReviewService,
)
from app.ai.software_engineer.autonomous_work_store import AutonomousWorkStore
from app.ai.unified_intent_router import UnifiedIntentRouter


class _Session:
    def __init__(
        self,
        session_id,
        *,
        target,
        source_hash,
        metadata,
        status="READY_FOR_APPROVAL",
        corrupt_artifact=False,
    ):
        self.session_id = session_id
        self.target = target
        self.source_hash = source_hash
        self.metadata = dict(metadata)
        self.status = status
        self.corrupt_artifact = corrupt_artifact

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "status": self.status,
            "target": self.target,
            "title": f"Patch {self.target}",
            "changed_files": [self.target],
            "changed_lines": 2,
            "source_hash": self.source_hash,
            "proposed_hash": "proposed-" + self.session_id,
            "fingerprint": "confirm-" + self.session_id,
            "risk_score": 8.0,
            "confidence": 0.99,
            "metadata": dict(self.metadata),
            "validation": {
                "workspace": {
                    "success": True,
                    "tests": {"success": True, "count": 7},
                },
            },
        }


class _SessionStore:
    def __init__(self):
        self.sessions = {}

    def load_session(self, session_id):
        if session_id not in self.sessions:
            raise FileNotFoundError(session_id)
        return self.sessions[session_id]

    def discard(self, session_id):
        session = self.load_session(session_id)
        if session.status == "DEPLOYED":
            raise ValueError("deployed")
        session.status = "DISCARDED"
        return session


class _Workspace:
    @staticmethod
    def verify_artifacts(session):
        if session.corrupt_artifact:
            raise ValueError("artifact mismatch")
        return {"original": "a", "proposed": "b", "diff": "-a\n+b\n"}


class B231B240AutonomousDevelopment31Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "app").mkdir(parents=True)
        self.session_store = _SessionStore()
        self.safe = SimpleNamespace(
            store=self.session_store,
            workspace=_Workspace(),
        )
        self.work_store = AutonomousWorkStore(self.root)
        self.campaign = self.work_store.new_campaign(requested_tasks=3)
        self.campaign.status = "READY_FOR_APPROVAL"
        self.review = AutonomousWorkReviewService(
            self.root,
            store=self.work_store,
            safe_development=self.safe,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _add_patch(
        self,
        index,
        *,
        target=None,
        status="READY_FOR_APPROVAL",
        corrupt_artifact=False,
        metadata_updates=None,
    ):
        target = target or f"app/module_{index}.py"
        path = self.root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(f"value = {index}\n", encoding="utf-8")
        source_hash = hashlib.sha256(
            path.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        item_id = f"work-item-{index:04d}"
        task_fingerprint = f"task-{index:04d}"
        session_id = f"safe-dev-review{index:04d}"
        metadata = {
            "campaign_id": self.campaign.campaign_id,
            "work_item_id": item_id,
            "work_task_fingerprint": task_fingerprint,
            "automatic_approval": False,
            "automatic_deployment": False,
        }
        metadata.update(dict(metadata_updates or {}))
        session = _Session(
            session_id,
            target=target,
            source_hash=source_hash,
            metadata=metadata,
            status=status,
            corrupt_artifact=corrupt_artifact,
        )
        self.session_store.sessions[session_id] = session
        self.campaign.items.append({
            "item_id": item_id,
            "status": status,
            "task": {
                "target": target,
                "title": f"Patch {index}",
                "risk_score": 8.0,
                "confidence": 0.99,
            },
            "task_fingerprint": task_fingerprint,
            "safe_session_id": session_id,
            "risk": {"accepted": True, "tests": 7},
        })
        self.campaign.prepared_session_ids.append(session_id)
        self.campaign.prepared_tasks += 1
        self.work_store.save(self.campaign)
        return session, path

    def test_b231_maps_each_campaign_item_to_exact_session(self):
        self._add_patch(1)
        second, _ = self._add_patch(2)
        result = self.review.review(patch_index=2)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["selection"]["session_id"], second.session_id)
        self.assertEqual(result["selection"]["patch_index"], 2)
        self.assertTrue(result["selection"]["eligible_for_confirmation"])

    def test_b232_review_is_read_only_and_manifest_digest_is_deterministic(self):
        _, path = self._add_patch(1)
        before = path.read_bytes()
        first = self.review.review()
        second = self.review.review()
        self.assertEqual(first["manifest_digest"], second["manifest_digest"])
        self.assertEqual(before, path.read_bytes())
        self.assertFalse(first["project_files_modified"])
        self.assertFalse(first["auto_approve"])
        self.assertFalse(first["auto_deploy"])

    def test_b233_changed_live_source_blocks_old_patch(self):
        _, path = self._add_patch(1)
        path.write_text("value = 999\n", encoding="utf-8")
        result = self.review.review()
        self.assertEqual(result["status"], "CAMPAIGN_REVIEW_BLOCKED")
        self.assertIn("SOURCE_CHANGED", result["patches"][0]["blockers"])
        self.assertFalse(result["patches"][0]["eligible_for_confirmation"])

    def test_b234_corrupt_isolated_artifact_blocks_patch(self):
        self._add_patch(1, corrupt_artifact=True)
        result = self.review.review()
        self.assertIn(
            "ARTIFACT_INTEGRITY_FAILED",
            result["patches"][0]["blockers"],
        )

    def test_b235_duplicate_target_is_reported_as_campaign_conflict(self):
        self._add_patch(1, target="app/shared.py")
        self._add_patch(2, target="app/shared.py")
        result = self.review.review()
        self.assertEqual(result["summary"]["blocked"], 2)
        self.assertTrue(all(
            "TARGET_CONFLICT_IN_CAMPAIGN" in patch["blockers"]
            for patch in result["patches"]
        ))

    def test_b236_wrong_session_provenance_is_never_eligible(self):
        self._add_patch(
            1,
            metadata_updates={"campaign_id": "autodev-work-foreign0001"},
        )
        result = self.review.review()
        self.assertIn(
            "CAMPAIGN_OWNERSHIP_MISMATCH",
            result["patches"][0]["blockers"],
        )
        self.assertFalse(result["patches"][0]["eligible_for_confirmation"])

    def test_b237_discard_requires_exact_choice_and_preserves_other_patch(self):
        first, first_path = self._add_patch(1)
        second, second_path = self._add_patch(2)
        before = (first_path.read_bytes(), second_path.read_bytes())
        ambiguous = self.review.discard_patch()
        self.assertEqual(ambiguous["status"], "PATCH_SELECTION_REQUIRED")
        self.assertEqual(first.status, "READY_FOR_APPROVAL")
        self.assertEqual(second.status, "READY_FOR_APPROVAL")

        result = self.review.discard_patch(patch_index=2)
        self.assertTrue(result["success"], result)
        self.assertEqual(second.status, "DISCARDED")
        self.assertEqual(first.status, "READY_FOR_APPROVAL")
        self.assertEqual(before, (first_path.read_bytes(), second_path.read_bytes()))
        persisted = self.work_store.load(self.campaign.campaign_id)
        self.assertEqual(persisted.items[1]["status"], "DISCARDED")
        self.assertEqual(persisted.status, "READY_FOR_APPROVAL")

    def test_b238_resolving_last_patch_closes_review_without_deployment(self):
        session, path = self._add_patch(1)
        before = path.read_bytes()
        result = self.review.discard_patch(patch_index=1)
        persisted = self.work_store.load(self.campaign.campaign_id)
        self.assertEqual(result["status"], "PATCH_DISCARDED")
        self.assertEqual(session.status, "DISCARDED")
        self.assertEqual(persisted.status, "REVIEW_COMPLETED")
        self.assertEqual(before, path.read_bytes())

    def test_b238_external_deployment_state_is_reconciled(self):
        session, path = self._add_patch(1)
        before = path.read_bytes()
        session.status = "DEPLOYED"
        result = self.review.reconcile_campaign()
        persisted = self.work_store.load(self.campaign.campaign_id)
        self.assertEqual(result["status"], "CAMPAIGN_REVIEW_COMPLETED")
        self.assertGreaterEqual(result["reconciled_changes"], 2)
        self.assertEqual(persisted.status, "REVIEW_COMPLETED")
        self.assertEqual(persisted.items[0]["status"], "DEPLOYED")
        self.assertEqual(before, path.read_bytes())

    def test_b239_routes_review_and_exact_discard_but_blocks_deployment(self):
        router = UnifiedIntentRouter()
        review = router.route("pokaż poprawkę numer 2 kampanii AutoDev")
        discard = router.route("odrzuć poprawkę numer 2 kampanii AutoDev")
        blocked = router.route("wdroż poprawkę numer 2 kampanii AutoDev")
        self.assertEqual(review.intent, "autodev_campaign_review")
        self.assertEqual(review.entities["patch_index"], 2)
        self.assertEqual(discard.intent, "autodev_campaign_discard_patch")
        self.assertEqual(discard.entities["patch_index"], 2)
        self.assertEqual(blocked.intent, "autodev_deployment_blocked")
        thought = plan_autonomous_work_command(
            SimpleNamespace(),
            "pokaż listę poprawek kampanii AutoDev",
        )
        self.assertEqual(thought["handler"], "autonomous_work_review")
        self.assertTrue(thought["read_only"])
        self.assertFalse(thought["project_write"])

    def test_b240_config_and_source_freeze_manual_decision_gate(self):
        project = Path(__file__).resolve().parents[1]
        config = json.loads(
            (project / "config/b231_b240_autonomous_development_3_1.json")
            .read_text(encoding="utf-8")
        )
        safety = config["safety"]
        self.assertFalse(safety["bulk_deployment_supported"])
        self.assertFalse(safety["automatic_approval"])
        self.assertFalse(safety["automatic_deployment"])
        self.assertTrue(safety["manual_confirmation_required"])
        source = (
            project
            / "app/ai/software_engineer/autonomous_work_review_service.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(".deploy(", source)


if __name__ == "__main__":
    unittest.main()

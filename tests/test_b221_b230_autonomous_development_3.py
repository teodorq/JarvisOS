from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.unified_intent_router import UnifiedIntentRouter
from app.ai.software_engineer.autonomous_cycle_commands import (
    plan_autonomous_cycle_command,
)
from app.ai.software_engineer.autonomous_self_seeding import (
    AutonomousBacklogSelfSeeder,
)
from app.ai.software_engineer.autonomous_work_commands import (
    plan_autonomous_work_command,
)
from app.ai.software_engineer.autonomous_work_models import AutonomousWorkPolicy
from app.ai.software_engineer.autonomous_work_orchestrator import (
    AutonomousWorkOrchestrator,
)
from app.ai.software_engineer.autonomous_work_service import AutonomousWorkService
from app.ai.software_engineer.autonomous_work_store import AutonomousWorkStore
from app.ai.software_engineer.autonomous_cycle_models import (
    AutonomousBacklogCandidate,
)


def _candidate(index: int, *, risk: float = 20.0) -> AutonomousBacklogCandidate:
    return AutonomousBacklogCandidate(
        source="test",
        task_id=f"task-{index}",
        fingerprint=f"fingerprint-{index}",
        target=f"app/module_{index}.py",
        title=f"Improve module {index}",
        description="Evidence-bound maintenance task",
        issue_type="LONG_FUNCTION",
        status="PENDING",
        risk_score=risk,
        value_score=70.0,
        effort_score=10.0,
        confidence=0.95,
        final_score=65.0,
        metadata={"function": f"worker_{index}", "evidence": {"line": 1}},
    )


class _Backlog:
    def __init__(self, candidates):
        self.values = list(candidates)

    def candidates(self, *, excluded_fingerprints=None):
        excluded = set(excluded_fingerprints or set())
        return [item for item in self.values if item.fingerprint not in excluded]


class _Seeder:
    def seed_many(self, **kwargs):
        return {
            "success": False,
            "tasks": [],
            "files_scanned": 3,
        }


@dataclass
class _Session:
    session_id: str
    status: str
    metadata: dict
    target: str

    def to_dict(self):
        return _session_dict(
            self.target,
            self.session_id,
            metadata=self.metadata,
        )


class _SafeStore:
    def __init__(self):
        self.latest = None
        self.discarded = []

    def latest_session(self):
        return self.latest

    def load_session(self, session_id):
        if self.latest is None or self.latest.session_id != session_id:
            raise FileNotFoundError(session_id)
        return self.latest

    def discard(self, session_id):
        self.discarded.append(session_id)
        self.latest.status = "DISCARDED"
        return self.latest


class _SafeDevelopment:
    def __init__(self, *, unsafe_approval=False):
        self.store = _SafeStore()
        self.calls = []
        self.unsafe_approval = unsafe_approval

    def prepare(self, *, preview):
        target = preview["task"]["target"]
        metadata = dict(preview["task"]["metadata"])
        session_id = f"safe-dev-test{len(self.calls) + 1:04d}"
        self.calls.append(preview)
        value = _session_dict(
            target,
            session_id,
            metadata={
                **metadata,
                "automatic_approval": self.unsafe_approval,
                "automatic_deployment": False,
            },
        )
        self.store.latest = _Session(
            session_id,
            "READY_FOR_APPROVAL",
            value["metadata"],
            target,
        )
        return {
            "success": True,
            "status": "READY_FOR_APPROVAL",
            "session": value,
            "project_files_modified": False,
        }


class _SlowSafeDevelopment(_SafeDevelopment):
    def __init__(self, delay_seconds=0.06):
        super().__init__()
        self.delay_seconds = delay_seconds
        self.deadlines = []

    def prepare(self, *, preview, deadline_monotonic=None):
        self.deadlines.append(deadline_monotonic)
        time.sleep(self.delay_seconds)
        return super().prepare(preview=preview)


class _BudgetSafeDevelopment(_SafeDevelopment):
    def prepare(self, *, preview, deadline_monotonic=None):
        return {
            "success": False,
            "status": "RUNTIME_BUDGET_REACHED",
            "message": "budget reached",
            "project_files_modified": False,
        }


class _TrackingWorkStore(AutonomousWorkStore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.heartbeat_count = 0

    def heartbeat_lease(self, campaign_id, token):
        self.heartbeat_count += 1
        return super().heartbeat_lease(campaign_id, token)


class _LosingWorkStore(_TrackingWorkStore):
    def heartbeat_lease(self, campaign_id, token):
        self.heartbeat_count += 1
        return False


def _session_dict(target, session_id, *, metadata):
    return {
        "session_id": session_id,
        "status": "READY_FOR_APPROVAL",
        "target": target,
        "changed_files": [target],
        "changed_lines": 1,
        "risk_score": 8.0,
        "confidence": 0.99,
        "metadata": dict(metadata),
        "validation": {
            "static": {"success": True},
            "workspace": {
                "success": True,
                "tests": {"success": True, "count": 7},
            },
        },
    }


class _InstantOrchestrator:
    def __init__(self, store):
        self.store = store
        self.safe_development = SimpleNamespace(store=_SafeStore())
        self.started = threading.Event()

    def run(self, campaign_id, *, progress_callback=None):
        self.started.set()
        campaign = self.store.load(campaign_id)
        campaign.status = "READY_FOR_APPROVAL"
        self.store.save(campaign)
        return {"success": True, "status": campaign.status}


class B221B230AutonomousDevelopment3Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "app").mkdir(parents=True)
        for index in range(1, 5):
            (self.root / f"app/module_{index}.py").write_text(
                f'"""Module {index}."""\n\ndef worker_{index}():\n    return {index}\n',
                encoding="utf-8",
            )

    def tearDown(self):
        self.temporary.cleanup()

    def test_b221_routes_natural_multi_task_work_without_exact_phrase(self):
        decision = UnifiedIntentRouter().route(
            "Jarvis, pracuj samodzielnie nad projektem przez cztery kolejne "
            "zadania i niczego nie wdrażaj"
        )
        self.assertEqual(decision.intent, "autodev_campaign_start")
        self.assertEqual(decision.entities["max_tasks"], 4)
        self.assertFalse(decision.auto_approve)
        self.assertFalse(decision.auto_deploy)

    def test_b221_understands_installation_negation_and_positive_request(self):
        router = UnifiedIntentRouter()
        for command in (
            "pracuj samodzielnie nad projektem i niczego nie instaluj",
            "przygotuj serie poprawek bez automatycznej instalacji",
            "pracuj samodzielnie nad kodem i nie zainstaluj niczego",
        ):
            decision = router.route(command)
            self.assertIsNotNone(decision, command)
            self.assertEqual(decision.intent, "autodev_campaign_start", command)
            self.assertFalse(decision.auto_deploy)

        blocked = router.route(
            "pracuj samodzielnie nad projektem i od razu zainstaluj poprawki"
        )
        self.assertIsNotNone(blocked)
        self.assertEqual(blocked.intent, "autodev_deployment_blocked")

    def test_b221_routes_status_resume_and_cancel_by_concepts(self):
        router = UnifiedIntentRouter()
        self.assertEqual(
            router.route("jaki jest postęp samodzielnej pracy nad kodem").intent,
            "autodev_campaign_status",
        )
        self.assertEqual(
            router.route("wznów przerwaną pracę AutoDev po restarcie").intent,
            "autodev_campaign_resume",
        )
        self.assertEqual(
            router.route("zatrzymaj samodzielną pracę nad projektem").intent,
            "autodev_campaign_cancel",
        )

    def test_b221_blocks_deployment_before_legacy_router(self):
        decision = UnifiedIntentRouter().route(
            "pracuj samodzielnie nad kodem i od razu wdróż wszystko"
        )
        self.assertEqual(decision.intent, "autodev_deployment_blocked")
        brain = SimpleNamespace(cognitive=MagicMock())
        thought = BrainCommandRouter().think(brain, "autodev przygotuj i wdroż patch")
        self.assertEqual(thought["handler"], "autonomous_work_deployment_blocked")
        self.assertFalse(thought["auto_deploy"])

    def test_b221_does_not_capture_calendar_or_recovery_learning(self):
        router = UnifiedIntentRouter()
        self.assertIsNone(router.route("uruchom cykl kalendarza dla projektu spotkania"))
        self.assertIsNone(router.route("uruchom cykl uczenia napraw"))

    def test_b221_keeps_single_cycle_compatibility(self):
        brain = MagicMock()
        thought = plan_autonomous_cycle_command(
            brain,
            "wykonaj jeden autonomiczny cykl rozwoju bez wdrażania",
        )
        self.assertEqual(thought["handler"], "autonomous_cycle_run")

    def test_b221_campaign_plan_is_background_and_workspace_only(self):
        thought = plan_autonomous_work_command(
            MagicMock(),
            "przygotuj serię pięciu bezpiecznych poprawek projektu",
        )
        self.assertEqual(thought["handler"], "autonomous_work_start")
        self.assertTrue(thought["background"])
        self.assertTrue(thought["workspace_only"])
        self.assertFalse(thought["project_write"])

    def test_b222_seeds_diverse_backlog_from_one_project_scan(self):
        for index in range(1, 4):
            body = "".join("    value += 1\n" for _ in range(121))
            (self.root / f"app/module_{index}.py").write_text(
                f"def worker_{index}(value):\n{body}    return value\n",
                encoding="utf-8",
            )
        result = AutonomousBacklogSelfSeeder(self.root).seed_many(limit=3)
        self.assertTrue(result["success"], result)
        self.assertEqual(len(result["tasks"]), 3)
        self.assertEqual(len({item["target"] for item in result["tasks"]}), 3)
        self.assertTrue(all(item["metadata"]["evidence"] for item in result["tasks"]))

    def test_b223_store_round_trips_campaign_and_events(self):
        store = AutonomousWorkStore(self.root)
        campaign = store.new_campaign(requested_tasks=3)
        store.event(campaign, "TEST_CHECKPOINT", value=7)
        store.save(campaign)
        loaded = store.load(campaign.campaign_id)
        self.assertEqual(loaded.requested_tasks, 3)
        self.assertEqual(loaded.events[-1]["event"], "TEST_CHECKPOINT")

    def test_b223_worker_lease_prevents_duplicate_runner(self):
        store = AutonomousWorkStore(
            self.root,
            policy=AutonomousWorkPolicy(lease_seconds=30),
        )
        campaign = store.new_campaign(requested_tasks=2)
        self.assertTrue(store.acquire_lease(campaign, "worker-a"))
        self.assertFalse(store.acquire_lease(campaign, "worker-b"))
        store.release_lease(campaign, "worker-a")
        self.assertTrue(store.acquire_lease(campaign, "worker-b"))
        store.release_lease(campaign, "worker-b")

    def test_b223_completed_worker_response_has_no_stale_lease(self):
        orchestrator, store, _ = self._orchestrator([_candidate(1)])
        campaign = store.new_campaign(requested_tasks=1)
        result = orchestrator.run(campaign.campaign_id)
        self.assertEqual(result["campaign"]["lease_token"], "")
        self.assertEqual(result["campaign"]["lease_expires_at"], "")

    def test_b226_other_campaigns_do_not_repeat_the_same_task(self):
        candidate = _candidate(1)
        first, first_store, _ = self._orchestrator([candidate])
        campaign = first_store.new_campaign(requested_tasks=1)
        self.assertTrue(first.run(campaign.campaign_id)["success"])
        second = AutonomousWorkOrchestrator(
            self.root,
            policy=first.policy,
            store=first_store,
            backlog=_Backlog([candidate]),
            seeder=_Seeder(),
            safe_development=_SafeDevelopment(),
        )
        next_campaign = first_store.new_campaign(requested_tasks=1)
        result = second.run(next_campaign.campaign_id)
        self.assertEqual(result["status"], "NO_PREPARABLE_TASK")
        self.assertEqual(result["campaign"]["prepared_tasks"], 0)

    def _orchestrator(self, candidates, *, safe=None, policy=None):
        policy = policy or AutonomousWorkPolicy(max_tasks=5)
        store = AutonomousWorkStore(self.root, policy=policy)
        safe = safe or _SafeDevelopment()
        return (
            AutonomousWorkOrchestrator(
                self.root,
                policy=policy,
                store=store,
                backlog=_Backlog(candidates),
                seeder=_Seeder(),
                safe_development=safe,
            ),
            store,
            safe,
        )

    def test_b224_prepares_multiple_consecutive_patches(self):
        orchestrator, store, safe = self._orchestrator(
            [_candidate(1), _candidate(2), _candidate(3)]
        )
        campaign = store.new_campaign(requested_tasks=3)
        before = {
            path.name: path.read_bytes() for path in (self.root / "app").glob("*.py")
        }
        result = orchestrator.run(campaign.campaign_id)
        after = {
            path.name: path.read_bytes() for path in (self.root / "app").glob("*.py")
        }
        self.assertTrue(result["success"], result)
        self.assertEqual(result["campaign"]["prepared_tasks"], 3)
        self.assertEqual(len(safe.calls), 3)
        self.assertEqual(before, after)

    def test_b225_rejects_patch_that_requests_automatic_approval(self):
        policy = AutonomousWorkPolicy(max_tasks=1, max_failures=1)
        orchestrator, store, _ = self._orchestrator(
            [_candidate(1)],
            safe=_SafeDevelopment(unsafe_approval=True),
            policy=policy,
        )
        campaign = store.new_campaign(requested_tasks=1)
        result = orchestrator.run(campaign.campaign_id)
        self.assertFalse(result["success"])
        risk = result["campaign"]["items"][0]["risk"]
        self.assertIn("AUTOMATIC_APPROVAL_FORBIDDEN", risk["reasons"])
        self.assertFalse(result["auto_approve"])
        self.assertFalse(result["auto_deploy"])

    def test_b225_risk_report_aggregates_tests(self):
        orchestrator, store, _ = self._orchestrator([_candidate(1), _candidate(2)])
        campaign = store.new_campaign(requested_tasks=2)
        result = orchestrator.run(campaign.campaign_id)
        summary = result["campaign"]["risk_summary"]
        self.assertEqual(summary["total_tests"], 14)
        self.assertTrue(summary["project_sources_unchanged"])

    def test_b227_recovery_adopts_completed_inflight_session(self):
        orchestrator, store, safe = self._orchestrator([])
        campaign = store.new_campaign(requested_tasks=1)
        candidate = _candidate(1)
        campaign.status = "RECOVERING"
        campaign.current_task_fingerprint = candidate.fingerprint
        campaign.items.append({
            "item_id": "work-item-recovery",
            "status": "PREPARING",
            "task": candidate.to_dict(),
            "task_fingerprint": candidate.fingerprint,
        })
        store.save(campaign)
        metadata = {
            "campaign_id": campaign.campaign_id,
            "work_task_fingerprint": candidate.fingerprint,
            "automatic_approval": False,
            "automatic_deployment": False,
        }
        safe.store.latest = _Session(
            "safe-dev-recovery01",
            "READY_FOR_APPROVAL",
            metadata,
            candidate.target,
        )
        result = orchestrator.run(campaign.campaign_id)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["campaign"]["prepared_tasks"], 1)
        self.assertEqual(len(safe.calls), 0)

    def test_b227_dead_process_lease_is_recovered_without_timeout(self):
        store = AutonomousWorkStore(self.root)
        campaign = store.new_campaign(requested_tasks=1)
        campaign.status = "RUNNING"
        campaign.lease_token = "dead-worker"
        campaign.lease_expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat()
        store.save(campaign)
        store._atomic_json(store.lease_path, {
            "campaign_id": campaign.campaign_id,
            "token": "dead-worker",
            "pid": 2147483647,
            "expires_at": campaign.lease_expires_at,
        })
        self.assertEqual(store.recover_interrupted(), [campaign.campaign_id])
        recovered = store.load(campaign.campaign_id)
        self.assertEqual(recovered.status, "RECOVERING")
        self.assertFalse(store.lease_path.exists())

    def test_b228_service_starts_worker_without_blocking_caller(self):
        policy = AutonomousWorkPolicy(max_tasks=2)
        store = AutonomousWorkStore(self.root, policy=policy)
        orchestrator = _InstantOrchestrator(store)
        service = AutonomousWorkService(
            self.root,
            policy=policy,
            store=store,
            orchestrator=orchestrator,
        )
        result = service.start(max_tasks=2, background=True)
        self.assertEqual(result["status"], "CAMPAIGN_STARTED")
        self.assertTrue(orchestrator.started.wait(1.0))
        self.assertTrue(service.wait(1.0))
        self.assertEqual(service.status()["status"], "READY_FOR_APPROVAL")

    def test_b228_heartbeat_renews_lease_during_slow_preparation(self):
        policy = AutonomousWorkPolicy(
            max_tasks=1,
            max_runtime_seconds=5,
            lease_seconds=10,
        )
        store = _TrackingWorkStore(self.root, policy=policy)
        safe = _SlowSafeDevelopment()
        orchestrator = AutonomousWorkOrchestrator(
            self.root,
            policy=policy,
            store=store,
            backlog=_Backlog([_candidate(1)]),
            seeder=_Seeder(),
            safe_development=safe,
            heartbeat_interval_seconds=0.01,
        )
        campaign = store.new_campaign(requested_tasks=1)
        result = orchestrator.run(campaign.campaign_id)
        self.assertTrue(result["success"], result)
        self.assertGreaterEqual(store.heartbeat_count, 1)
        self.assertEqual(len(safe.deadlines), 1)
        self.assertIsNotNone(safe.deadlines[0])
        self.assertFalse(store.lease_path.exists())

    def test_b228_lost_heartbeat_marks_campaign_as_safety_violation(self):
        policy = AutonomousWorkPolicy(
            max_tasks=1,
            max_runtime_seconds=5,
            lease_seconds=10,
        )
        store = _LosingWorkStore(self.root, policy=policy)
        orchestrator = AutonomousWorkOrchestrator(
            self.root,
            policy=policy,
            store=store,
            backlog=_Backlog([_candidate(1)]),
            seeder=_Seeder(),
            safe_development=_SlowSafeDevelopment(),
            heartbeat_interval_seconds=0.01,
        )
        campaign = store.new_campaign(requested_tasks=1)
        result = orchestrator.run(campaign.campaign_id)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "SAFETY_VIOLATION")
        self.assertTrue(result["campaign"]["errors"])
        self.assertFalse(store.lease_path.exists())

    def test_b228_runtime_budget_is_retry_safe_and_not_a_task_failure(self):
        policy = AutonomousWorkPolicy(max_tasks=1, max_runtime_seconds=5)
        orchestrator, store, _ = self._orchestrator(
            [_candidate(1)],
            safe=_BudgetSafeDevelopment(),
            policy=policy,
        )
        campaign = store.new_campaign(requested_tasks=1)
        result = orchestrator.run(campaign.campaign_id)
        persisted = store.load(campaign.campaign_id)
        self.assertEqual(result["status"], "RECOVERING")
        self.assertEqual(persisted.failed_tasks, 0)
        self.assertEqual(persisted.items[0]["status"], "INTERRUPTED_RETRY_SAFE")
        self.assertNotIn(_candidate(1).fingerprint, persisted.attempted_fingerprints)
        self.assertFalse(store.lease_path.exists())

    def test_b229_legacy_brain_fallback_disables_automatic_approval(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "app/ai/brain_command_router.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("'auto_approve': True", source)
        self.assertIn("'auto_approve': False", source)

    def test_b230_config_freezes_release_gate(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "config/b221_b230_autonomous_development_3.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["stage"], "B221-B230")
        self.assertFalse(config["safety"]["auto_approve"])
        self.assertFalse(config["safety"]["auto_deploy"])
        self.assertTrue(config["safety"]["stop_before_deployment"])

    def test_source_contract_uses_one_router_and_no_deployment_call(self):
        root = Path(__file__).resolve().parents[1]
        cycle_commands = (
            root / "app/ai/software_engineer/autonomous_cycle_commands.py"
        ).read_text(encoding="utf-8")
        orchestrator = (
            root / "app/ai/software_engineer/autonomous_work_orchestrator.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_RUN_MARKERS", cycle_commands)
        self.assertIn("DEFAULT_INTENT_ROUTER", cycle_commands)
        self.assertNotIn(".deploy(", orchestrator)
        self.assertNotIn("C:" + "\\JarvisAI", orchestrator)


if __name__ == "__main__":
    unittest.main()

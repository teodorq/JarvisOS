from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from app.ai.software_engineer.long_running_autonomy_scheduler import (
    LongRunningAutonomyScheduler,
)
from app.ai.software_engineer.long_running_autonomy_service import (
    LongRunningAutonomyService,
)
from app.ai.software_engineer.long_running_autonomy_store import (
    LongRunningAutonomyStore,
)
from app.ai.software_engineer.long_running_resource_guard import (
    LongRunningResourceGuard,
)


NOW = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)


class FakeWorkflow:
    def __init__(self, responses: list[dict] | None = None) -> None:
        self.responses = list(
            responses
            or [{
                "success": True,
                "status": "FULL_AUTONOMY_COMPLETED",
                "autonomy_run_id": "autonomy-completed",
                "progress_percent": 100.0,
                "errors": [],
            }]
        )
        self.run_calls: list[str] = []
        self.execute_calls: list[str] = []

    def _next(self) -> dict:
        if len(self.responses) > 1:
            return dict(self.responses.pop(0))
        return dict(self.responses[0])

    def run(self, objective: str, *, context: dict | None = None) -> dict:
        self.run_calls.append(objective)
        return self._next()

    def execute(self, run_id: str, *, context: dict | None = None) -> dict:
        self.execute_calls.append(run_id)
        return self._next()

    def status(self, run_id: str) -> dict:
        return {
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": run_id,
            "errors": [],
        }


class B53RuntimeQueueFixTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def service(
        self,
        responses: list[dict] | None = None,
    ) -> LongRunningAutonomyService:
        guard = LongRunningResourceGuard(
            self.root,
            sample_provider=lambda: {
                "cpu_percent": 10.0,
                "memory_percent": 20.0,
                "disk_free_gb": 100.0,
                "on_ac_power": True,
            },
        )
        return LongRunningAutonomyService(
            self.root,
            workflow=FakeWorkflow(responses),
            resource_guard=guard,
            clock=lambda: NOW,
        )

    def test_scheduler_skips_exhausted_job(self) -> None:
        scheduler = LongRunningAutonomyScheduler()
        jobs = [{
            "job_id": "longrun-old",
            "state": "SCHEDULED",
            "attempts": 5,
            "max_attempts": 3,
            "priority": 100,
            "next_run_at": NOW.isoformat(),
        }, {
            "job_id": "longrun-next",
            "state": "QUEUED",
            "attempts": 0,
            "max_attempts": 3,
            "priority": 10,
            "next_run_at": NOW.isoformat(),
        }]

        selected = scheduler.due_jobs(jobs, now=NOW, limit=1)

        self.assertEqual(selected[0]["job_id"], "longrun-next")

    def test_tick_fails_exhausted_and_runs_next_job_same_cycle(self) -> None:
        service = self.service()
        exhausted_id = service.enqueue(
            "stare zadanie",
            context={"priority": 100, "max_attempts": 3},
        )["job_id"]
        exhausted = service.store.get_job(exhausted_id)
        exhausted.update({
            "state": "SCHEDULED",
            "attempts": 5,
            "next_run_at": NOW.isoformat(),
        })
        service.store.save_job(exhausted)

        next_id = service.enqueue(
            "nowe zadanie",
            context={"priority": 10},
        )["job_id"]

        result = service.tick(now=NOW)

        self.assertEqual(
            service.store.get_job(exhausted_id)["state"],
            "FAILED",
        )
        self.assertEqual(
            service.store.get_job(next_id)["state"],
            "COMPLETED",
        )
        self.assertEqual(result["status"], "LONG_RUNNING_TICK_COMPLETED")

    def test_paused_result_at_final_attempt_becomes_failed(self) -> None:
        service = self.service([{
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": "autonomy-paused",
            "errors": [],
        }])
        job_id = service.enqueue(
            "cel",
            context={"max_attempts": 1},
        )["job_id"]

        service.tick(now=NOW)
        job = service.store.get_job(job_id)

        self.assertEqual(job["state"], "FAILED")
        self.assertEqual(job["attempts"], 1)
        self.assertEqual(job["next_run_at"], "")
        self.assertIn("limit prób", job["last_error"])

    def test_force_recovery_fails_exhausted_running_job(self) -> None:
        service = self.service()
        job_id = service.enqueue(
            "cel",
            context={"max_attempts": 3},
        )["job_id"]
        job = service.store.get_job(job_id)
        job.update({
            "state": "RUNNING",
            "attempts": 6,
            "heartbeat_at": NOW.isoformat(),
        })
        service.store.save_job(job)

        recovered = service.recover_interrupted(now=NOW, force=True)

        self.assertEqual(len(recovered), 1)
        saved = service.store.get_job(job_id)
        self.assertEqual(saved["state"], "FAILED")
        self.assertEqual(saved["next_run_at"], "")

    def test_resume_failed_job_resets_attempt_budget(self) -> None:
        service = self.service()
        job_id = service.enqueue(
            "cel",
            context={"max_attempts": 3},
        )["job_id"]
        job = service.store.get_job(job_id)
        job.update({
            "state": "FAILED",
            "attempts": 3,
            "autonomy_run_id": "autonomy-old",
            "completed_at": NOW.isoformat(),
        })
        service.store.save_job(job)

        result = service.resume_job(job_id)

        self.assertTrue(result["success"])
        self.assertEqual(result["job"]["state"], "QUEUED")
        self.assertEqual(result["job"]["attempts"], 0)
        self.assertEqual(result["job"]["autonomy_run_id"], "")
        self.assertEqual(
            result["job"]["metadata"]["manual_restarts"],
            1,
        )

    def test_store_compacts_large_job_result(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        large = {
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": "autonomy-large",
            "progress_percent": 25.0,
            "runtime": {"last_result": {"payload": "x" * 100_000}},
            "autonomy_run": {
                "events": [{"payload": "x" * 100_000}],
                "progress_percent": 25.0,
            },
        }
        job = {
            "job_id": "longrun-large",
            "objective": "cel",
            "last_result": large,
        }

        saved = store.save_job(job)

        self.assertEqual(
            saved["last_result"]["status"],
            "FULL_AUTONOMY_PAUSED",
        )
        self.assertNotIn("runtime", saved["last_result"])
        self.assertNotIn("autonomy_run", saved["last_result"])
        self.assertLess(
            len(json.dumps(saved["last_result"])),
            5000,
        )

    def test_runtime_last_result_never_contains_runtime_snapshot(self) -> None:
        service = self.service()

        service.tick(now=NOW)
        runtime = service.store.runtime()
        last_result = runtime["last_result"]

        self.assertEqual(
            last_result["status"],
            "LONG_RUNNING_TICK_IDLE",
        )
        self.assertNotIn("runtime", last_result)
        self.assertNotIn("policy", last_result)
        self.assertNotIn("jobs", last_result)

    def test_store_compact_migrates_legacy_recursive_payload(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        payload = store.load()
        payload["runtime"]["last_result"] = {
            "status": "LONG_RUNNING_TICK_IDLE",
            "runtime": {
                "last_result": {
                    "runtime": {
                        "payload": "x" * 200_000,
                    }
                }
            },
        }
        store._store.save(payload)
        before = store.path.stat().st_size

        store.compact()
        after = store.path.stat().st_size
        compacted = store.runtime()["last_result"]

        self.assertLess(after, before)
        self.assertEqual(
            compacted["status"],
            "LONG_RUNNING_TICK_IDLE",
        )
        self.assertNotIn("runtime", compacted)

    def test_repair_queue_fixes_snapshot_without_executing_jobs(self) -> None:
        service = self.service()
        old_id = service.enqueue(
            "stare",
            context={"max_attempts": 3},
        )["job_id"]
        old = service.store.get_job(old_id)
        old.update({
            "state": "RUNNING",
            "attempts": 6,
            "last_result": {
                "status": "FULL_AUTONOMY_PAUSED",
                "runtime": {"payload": "x" * 100_000},
            },
        })
        service.store.save_job(old)

        next_id = service.enqueue("następne")["job_id"]
        result = service.repair_queue(
            force_running=True,
            now=NOW,
        )

        self.assertEqual(result["status"], "LONG_RUNNING_QUEUE_REPAIRED")
        self.assertEqual(service.store.get_job(old_id)["state"], "FAILED")
        self.assertEqual(service.store.get_job(next_id)["state"], "QUEUED")
        self.assertEqual(
            len(service.workflow.run_calls),
            0,
        )


if __name__ == "__main__":
    unittest.main()

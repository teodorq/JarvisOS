"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_command_router import (
    SoftwareEngineerCommandRouter,
)
from app.ai.software_engineer.long_running_autonomy_models import (
    LongRunningJob,
)
from app.ai.software_engineer.long_running_autonomy_scheduler import (
    LongRunningAutonomyScheduler,
)
from app.ai.software_engineer.long_running_autonomy_service import (
    LongRunningAutonomyService,
    bootstrap_long_running_autonomy,
)
from app.ai.software_engineer.long_running_autonomy_store import (
    LongRunningAutonomyStore,
)
from app.ai.software_engineer.long_running_autonomy_watchdog import (
    LongRunningAutonomyWatchdog,
)
from app.ai.software_engineer.long_running_resource_guard import (
    LongRunningResourceGuard,
)
from app.ai.software_engineer.software_engineer_long_running_formatter import (
    format_long_running_autonomy_response,
)
from app.ai.software_engineer.software_engineer_long_running_router import (
    SoftwareEngineerLongRunningRouter,
)
from app.gui.command_safety import (
    is_read_only_learning_command,
)


NOW = datetime(2026, 7, 16, 20, 0, tzinfo=timezone.utc)


class FakeWorkflow:
    def __init__(
        self,
        responses: list[dict] | None = None,
    ) -> None:
        self.responses = list(
            responses
            or [
                {
                    "success": True,
                    "status": "FULL_AUTONOMY_COMPLETED",
                    "autonomy_run_id": "autonomy-success",
                    "errors": [],
                }
            ]
        )
        self.run_calls: list[tuple[str, dict]] = []
        self.execute_calls: list[tuple[str, dict]] = []
        self.status_calls: list[str] = []

    def _next(self) -> dict:
        if len(self.responses) > 1:
            return dict(self.responses.pop(0))
        return dict(self.responses[0])

    def run(
        self,
        objective: str,
        *,
        context: dict | None = None,
    ) -> dict:
        self.run_calls.append(
            (objective, dict(context or {}))
        )
        return self._next()

    def execute(
        self,
        run_id: str,
        *,
        context: dict | None = None,
    ) -> dict:
        self.execute_calls.append(
            (run_id, dict(context or {}))
        )
        return self._next()

    def status(
        self,
        run_id: str,
    ) -> dict:
        self.status_calls.append(run_id)
        return {
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": run_id,
            "errors": [],
        }


class B53LongRunningAutonomyTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()
        self.clock_value = NOW

    def tearDown(self) -> None:
        self.temp.cleanup()

    def clock(self) -> datetime:
        return self.clock_value

    def service(
        self,
        *,
        workflow: FakeWorkflow | None = None,
        sample: dict | None = None,
    ) -> LongRunningAutonomyService:
        guard = LongRunningResourceGuard(
            self.root,
            sample_provider=lambda: dict(
                sample
                or {
                    "cpu_percent": 10.0,
                    "memory_percent": 20.0,
                    "disk_free_gb": 100.0,
                    "on_ac_power": True,
                }
            ),
        )
        return LongRunningAutonomyService(
            self.root,
            workflow=workflow or FakeWorkflow(),
            resource_guard=guard,
            clock=self.clock,
        )

    def test_store_persists_jobs_and_runtime(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        job = LongRunningJob(
            objective="Cel",
            job_id="longrun-persist",
        )
        store.save_job(job)
        store.update_runtime({"enabled": True})

        reloaded = LongRunningAutonomyStore(self.root)

        self.assertEqual(
            reloaded.get_job("longrun-persist")["objective"],
            "Cel",
        )
        self.assertTrue(reloaded.runtime()["enabled"])

    def test_store_policy_is_bounded_and_never_auto_approves(
        self,
    ) -> None:
        store = LongRunningAutonomyStore(self.root)

        policy = store.update_policy({
            "max_cpu_percent": 500,
            "max_memory_percent": -1,
            "max_parallel_jobs": 99,
            "auto_approve": True,
        })

        self.assertEqual(policy["max_cpu_percent"], 98.0)
        self.assertEqual(policy["max_memory_percent"], 20.0)
        self.assertEqual(policy["max_parallel_jobs"], 3)
        self.assertFalse(policy["auto_approve"])

    def test_store_records_bounded_events(self) -> None:
        store = LongRunningAutonomyStore(
            self.root,
            max_events=100,
        )
        for index in range(120):
            store.record_event(
                "EVENT",
                metadata={"index": index},
            )

        self.assertEqual(len(store.load()["events"]), 100)

    def test_scheduler_normalizes_immediate_and_interval(
        self,
    ) -> None:
        scheduler = LongRunningAutonomyScheduler()

        immediate = scheduler.normalize({}, now=NOW)
        interval = scheduler.normalize(
            {
                "type": "interval",
                "interval_minutes": 5,
            },
            now=NOW,
        )

        self.assertEqual(immediate["type"], "immediate")
        self.assertEqual(
            immediate["next_run_at"],
            NOW.isoformat(),
        )
        self.assertEqual(
            interval["interval_seconds"],
            300,
        )

    def test_scheduler_daily_moves_to_next_day_when_time_passed(
        self,
    ) -> None:
        scheduler = LongRunningAutonomyScheduler()

        schedule = scheduler.normalize(
            {
                "type": "daily",
                "hour": 19,
                "minute": 30,
            },
            now=NOW,
        )

        self.assertEqual(
            schedule["next_run_at"],
            datetime(
                2026,
                7,
                17,
                19,
                30,
                tzinfo=timezone.utc,
            ).isoformat(),
        )

    def test_scheduler_orders_due_jobs_by_priority(
        self,
    ) -> None:
        scheduler = LongRunningAutonomyScheduler()
        jobs = [
            {
                "job_id": "longrun-low",
                "state": "QUEUED",
                "priority": 10,
                "next_run_at": NOW.isoformat(),
            },
            {
                "job_id": "longrun-high",
                "state": "QUEUED",
                "priority": 90,
                "next_run_at": NOW.isoformat(),
            },
        ]

        due = scheduler.due_jobs(
            jobs,
            now=NOW,
            limit=2,
        )

        self.assertEqual(
            [item["job_id"] for item in due],
            ["longrun-high", "longrun-low"],
        )

    def test_resource_guard_blocks_cpu_memory_and_disk(
        self,
    ) -> None:
        guard = LongRunningResourceGuard(
            self.root,
            sample_provider=lambda: {
                "cpu_percent": 99,
                "memory_percent": 95,
                "disk_free_gb": 0.1,
                "on_ac_power": False,
            },
        )

        result = guard.evaluate({
            "max_cpu_percent": 85,
            "max_memory_percent": 90,
            "min_disk_free_gb": 2,
            "require_ac_power": True,
        })

        self.assertFalse(result["allowed"])
        self.assertEqual(len(result["reasons"]), 4)

    def test_resource_guard_allows_safe_sample(self) -> None:
        guard = LongRunningResourceGuard(
            self.root,
            sample_provider=lambda: {
                "cpu_percent": 10,
                "memory_percent": 20,
                "disk_free_gb": 50,
                "on_ac_power": True,
            },
        )

        self.assertTrue(
            guard.evaluate({})["allowed"]
        )

    def test_watchdog_recovers_stale_running_job(self) -> None:
        watchdog = LongRunningAutonomyWatchdog()
        job = LongRunningJob(
            objective="Cel",
            job_id="longrun-stale",
            state="RUNNING",
            heartbeat_at=(
                NOW - timedelta(minutes=10)
            ).isoformat(),
        ).to_dict()

        recovered = watchdog.recover(
            [job],
            stale_after_seconds=300,
            now=NOW,
        )

        self.assertEqual(recovered[0]["state"], "RECOVERING")

    def test_watchdog_fails_stale_job_when_restart_disabled(
        self,
    ) -> None:
        watchdog = LongRunningAutonomyWatchdog()
        job = LongRunningJob(
            objective="Cel",
            job_id="longrun-fail-stale",
            state="RUNNING",
            restart_policy="FAIL",
            heartbeat_at=(
                NOW - timedelta(minutes=10)
            ).isoformat(),
        ).to_dict()

        recovered = watchdog.recover(
            [job],
            stale_after_seconds=300,
            now=NOW,
        )

        self.assertEqual(recovered[0]["state"], "FAILED")

    def test_service_enqueue_never_persists_auto_approve(
        self,
    ) -> None:
        service = self.service()

        result = service.enqueue(
            "Bezpieczny cel",
            context={
                "auto_approve": True,
                "auto_rollback": True,
            },
        )

        self.assertEqual(
            result["status"],
            "LONG_RUNNING_JOB_ENQUEUED",
        )
        self.assertFalse(
            result["job"]["execution_context"]["auto_approve"]
        )

    def test_service_tick_completes_immediate_job(self) -> None:
        workflow = FakeWorkflow()
        service = self.service(workflow=workflow)
        job_id = service.enqueue("Cel")["job_id"]

        result = service.tick(now=NOW)

        self.assertEqual(
            result["status"],
            "LONG_RUNNING_TICK_COMPLETED",
        )
        job = service.store.get_job(job_id)
        self.assertEqual(job["state"], "COMPLETED")
        self.assertEqual(
            job["autonomy_run_id"],
            "autonomy-success",
        )

    def test_service_waits_when_resources_are_blocked(self) -> None:
        service = self.service(
            sample={
                "cpu_percent": 99.0,
                "memory_percent": 20.0,
                "disk_free_gb": 100.0,
                "on_ac_power": True,
            }
        )
        job_id = service.enqueue("Cel")["job_id"]

        service.tick(now=NOW)

        job = service.store.get_job(job_id)
        self.assertEqual(job["state"], "WAITING_RESOURCES")
        self.assertIn("CPU", job["last_error"])

    def test_service_schedules_retry_after_failure(self) -> None:
        workflow = FakeWorkflow([
            {
                "success": False,
                "status": "FULL_AUTONOMY_FAILED",
                "autonomy_run_id": "autonomy-failed",
                "errors": ["Błąd"],
            }
        ])
        service = self.service(workflow=workflow)
        job_id = service.enqueue(
            "Cel",
            context={"max_attempts": 2},
        )["job_id"]

        service.tick(now=NOW)

        job = service.store.get_job(job_id)
        self.assertEqual(job["state"], "SCHEDULED")
        self.assertEqual(job["attempts"], 1)

    def test_service_fails_after_max_attempts(self) -> None:
        workflow = FakeWorkflow([
            {
                "success": False,
                "status": "FULL_AUTONOMY_FAILED",
                "autonomy_run_id": "autonomy-failed",
                "errors": ["Błąd"],
            }
        ])
        service = self.service(workflow=workflow)
        job_id = service.enqueue(
            "Cel",
            context={"max_attempts": 1},
        )["job_id"]

        service.tick(now=NOW)

        self.assertEqual(
            service.store.get_job(job_id)["state"],
            "FAILED",
        )

    def test_service_reschedules_recurring_job(self) -> None:
        service = self.service()
        job_id = service.enqueue(
            "Cel",
            context={
                "schedule": {
                    "type": "interval",
                    "interval_minutes": 5,
                }
            },
        )["job_id"]

        service.tick(now=NOW)

        job = service.store.get_job(job_id)
        self.assertEqual(job["state"], "SCHEDULED")
        self.assertEqual(job["attempts"], 0)
        self.assertEqual(len(job["run_history"]), 1)
        self.assertFalse(job["autonomy_run_id"])

    def test_service_resumes_existing_autonomy_run(self) -> None:
        workflow = FakeWorkflow([
            {
                "success": True,
                "status": "FULL_AUTONOMY_COMPLETED",
                "autonomy_run_id": "autonomy-existing",
                "errors": [],
            }
        ])
        service = self.service(workflow=workflow)
        result = service.enqueue("Cel")
        job = result["job"]
        job["autonomy_run_id"] = "autonomy-existing"
        service.store.save_job(job)

        service.tick(now=NOW)

        self.assertEqual(
            workflow.execute_calls[0][0],
            "autonomy-existing",
        )

    def test_service_pause_resume_and_cancel_job(self) -> None:
        service = self.service()
        job_id = service.enqueue("Cel")["job_id"]

        paused = service.pause_job(job_id)
        resumed = service.resume_job(job_id)
        cancelled = service.cancel_job(job_id)

        self.assertEqual(paused["job"]["state"], "PAUSED")
        self.assertEqual(resumed["job"]["state"], "QUEUED")
        self.assertEqual(cancelled["job"]["state"], "CANCELLED")

    def test_startup_force_recovers_recent_running_job(
        self,
    ) -> None:
        service = self.service()
        job = service.enqueue("Cel")["job"]
        job["state"] = "RUNNING"
        job["heartbeat_at"] = NOW.isoformat()
        service.store.save_job(job)

        recovered = service.recover_interrupted(
            now=NOW,
            force=True,
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(
            service.store.get_job(job["job_id"])["state"],
            "RECOVERING",
        )

    def test_service_recovers_interrupted_job(self) -> None:
        service = self.service()
        job = service.enqueue("Cel")["job"]
        job["state"] = "RUNNING"
        job["heartbeat_at"] = (
            NOW - timedelta(minutes=10)
        ).isoformat()
        service.store.save_job(job)

        recovered = service.recover_interrupted(now=NOW)

        self.assertEqual(len(recovered), 1)
        self.assertEqual(
            service.store.get_job(job["job_id"])["state"],
            "RECOVERING",
        )

    def test_service_status_reports_counts(self) -> None:
        service = self.service()
        service.enqueue("Cel A")
        service.enqueue("Cel B")

        result = service.status()

        self.assertEqual(result["counts"]["QUEUED"], 2)

    def test_service_update_policy_keeps_safety_invariants(
        self,
    ) -> None:
        service = self.service()

        result = service.update_policy({
            "auto_approve": True,
            "max_parallel_jobs": 10,
        })

        self.assertFalse(result["policy"]["auto_approve"])
        self.assertEqual(
            result["policy"]["max_parallel_jobs"],
            3,
        )

    def test_controller_accepts_long_running_gui_commands(
        self,
    ) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Pokaż status długotrwałej autonomii"
            )
        )
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Zaplanuj długotrwałą autonomię"
            )
        )

    def test_command_router_accepts_context_only_long_running_operation(
        self,
    ) -> None:
        service = self.service()
        controller = SimpleNamespace(
            project_root=self.root,
            long_running_autonomy_service=service,
            can_handle=lambda command: False,
            _normalize=lambda value: " ".join(
                str(value).casefold().split()
            ),
            _extract_objective=lambda command: "Cel z kontekstu",
            _is_multi_file_request=lambda command, context: False,
        )

        result = SoftwareEngineerCommandRouter().handle(
            controller,
            "dowolne polecenie",
            {
                "operation": "long_running_autonomy",
                "long_running_action": "status",
            },
        )

        self.assertEqual(
            result["status"],
            "LONG_RUNNING_AUTONOMY_STATUS",
        )

    def test_router_routes_status_command(self) -> None:
        service = self.service()
        controller = SimpleNamespace(
            project_root=self.root,
            long_running_autonomy_service=service,
            _normalize=lambda value: " ".join(
                str(value).casefold().split()
            ),
        )

        result = SoftwareEngineerLongRunningRouter().try_handle(
            controller,
            command="Pokaż status długotrwałej autonomii",
            objective="",
            context={},
        )

        self.assertEqual(
            result["status"],
            "LONG_RUNNING_AUTONOMY_STATUS",
        )

    def test_router_enqueues_long_running_goal(self) -> None:
        service = self.service()
        controller = SimpleNamespace(
            project_root=self.root,
            long_running_autonomy_service=service,
            _normalize=lambda value: " ".join(
                str(value).casefold().split()
            ),
        )

        result = SoftwareEngineerLongRunningRouter().try_handle(
            controller,
            command="Zaplanuj długotrwałą autonomię",
            objective="Ulepsz raportowanie",
            context={},
        )

        self.assertEqual(
            result["status"],
            "LONG_RUNNING_JOB_ENQUEUED",
        )

    def test_router_parses_interval_schedule_from_polish_command(
        self,
    ) -> None:
        service = self.service()
        controller = SimpleNamespace(
            project_root=self.root,
            long_running_autonomy_service=service,
            _normalize=lambda value: " ".join(
                str(value).casefold().split()
            ),
        )

        result = SoftwareEngineerLongRunningRouter().try_handle(
            controller,
            command=(
                "Zaplanuj długotrwałą autonomię co 30 minut"
            ),
            objective="Regularnie sprawdzaj projekt",
            context={},
        )

        self.assertEqual(
            result["job"]["schedule"]["type"],
            "interval",
        )
        self.assertEqual(
            result["job"]["schedule"]["interval_seconds"],
            1800,
        )

    def test_router_parses_resource_policy_from_polish_command(
        self,
    ) -> None:
        service = self.service()
        controller = SimpleNamespace(
            project_root=self.root,
            long_running_autonomy_service=service,
            _normalize=lambda value: " ".join(
                str(value).casefold().split()
            ),
        )

        result = SoftwareEngineerLongRunningRouter().try_handle(
            controller,
            command=(
                "Ustaw limity długiej autonomii: "
                "CPU 80%, RAM 85%, dysk minimum 5 GB, "
                "równolegle 2"
            ),
            objective="",
            context={},
        )

        self.assertEqual(
            result["status"],
            "LONG_RUNNING_POLICY_UPDATED",
        )
        self.assertEqual(
            result["policy"]["max_cpu_percent"],
            80.0,
        )
        self.assertEqual(
            result["policy"]["max_memory_percent"],
            85.0,
        )
        self.assertEqual(
            result["policy"]["min_disk_free_gb"],
            5.0,
        )
        self.assertEqual(
            result["policy"]["max_parallel_jobs"],
            2,
        )
        self.assertFalse(
            result["policy"]["auto_approve"]
        )

    def test_router_requires_job_id_for_job_action(self) -> None:
        controller = SimpleNamespace(
            project_root=self.root,
            long_running_autonomy_service=self.service(),
            _normalize=lambda value: " ".join(
                str(value).casefold().split()
            ),
        )

        result = SoftwareEngineerLongRunningRouter().try_handle(
            controller,
            command="Wstrzymaj zadanie długotrwałe",
            objective="",
            context={},
        )

        self.assertEqual(
            result["status"],
            "LONG_RUNNING_JOB_ID_REQUIRED",
        )

    def test_formatter_reports_supervisor_and_limits(self) -> None:
        text = format_long_running_autonomy_response({
            "status": "LONG_RUNNING_AUTONOMY_STATUS",
            "runtime": {
                "enabled": True,
                "cycles_completed": 3,
                "recovered_jobs": 1,
            },
            "policy": {
                "max_cpu_percent": 85,
                "max_memory_percent": 90,
                "min_disk_free_gb": 2,
                "max_parallel_jobs": 1,
            },
            "jobs": [],
            "counts": {},
            "errors": [],
        })

        self.assertIn("Nadzorca: AKTYWNY", text)
        self.assertIn("CPU 85%", text)

    def test_brain_formatter_routes_long_running_operation(
        self,
    ) -> None:
        formatter = BrainResponseFormatter()

        text = formatter._format_software_engineer_response({
            "success": True,
            "status": "LONG_RUNNING_AUTONOMY_STATUS",
            "operation": "long_running_autonomy",
            "runtime": {},
            "policy": {},
            "jobs": [],
            "errors": [],
        })

        self.assertIn("Długotrwała autonomia", text)

    def test_read_only_long_running_status_is_safe(self) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż status długotrwałej autonomii"
            )
        )
        self.assertFalse(
            is_read_only_learning_command(
                "Uruchom nadzorcę autonomii"
            )
        )

    def test_bootstrap_attaches_service_without_start_when_disabled(
        self,
    ) -> None:
        controller = SimpleNamespace(
            project_root=self.root,
        )

        service = bootstrap_long_running_autonomy(controller)

        self.assertIs(
            controller.long_running_autonomy_service,
            service,
        )
        self.assertFalse(service.is_running())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomous_self_repair import (
    AutonomousSelfRepair,
)
from app.ai.software_engineer.long_running_autonomy_models import (
    LongRunningJob,
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
from app.ai.software_engineer.software_engineer_long_running_formatter import (
    format_long_running_autonomy_response,
)
from tools.repair_b54_3_approval_lease import repair


NOW = datetime(2026, 7, 17, 14, 0, tzinfo=timezone.utc)


class Workflow:
    def __init__(
        self,
        response: dict | None = None,
        status_response: dict | None = None,
    ) -> None:
        self.response = response or {
            "success": True,
            "status": "FULL_AUTONOMY_COMPLETED",
            "autonomy_run_id": "autonomy-one",
            "execution": {"progress_percent": 100.0},
            "errors": [],
        }
        self.status_response = status_response or {
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": "autonomy-one",
            "execution": {"progress_percent": 0.0},
            "errors": [],
        }
        self.execute_contexts: list[dict] = []

    def status(self, run_id: str) -> dict:
        return {**self.status_response, "autonomy_run_id": run_id}

    def execute(self, run_id: str, *, context: dict | None = None) -> dict:
        self.execute_contexts.append(dict(context or {}))
        return {**self.response, "autonomy_run_id": run_id}

    def run(self, objective: str, *, context: dict | None = None) -> dict:
        self.execute_contexts.append(dict(context or {}))
        return dict(self.response)


class Diagnostics:
    def __init__(self, *, approval: bool = False) -> None:
        self.approval = approval

    def record_job_result(self, job, response, **kwargs):
        return {
            "diagnostic": {
                "diagnostic_id": "diagnostic-one",
                "category": (
                    "APPROVAL_REQUIRED" if self.approval else "SUCCESS"
                ),
                "severity": "INFO",
                "requires_approval": self.approval,
                "repairable": self.approval,
                "root_cause": (
                    "Wymagana jest akceptacja."
                    if self.approval
                    else ""
                ),
            }
        }


class B543ApprovalLeaseProgressTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def service(
        self,
        workflow: Workflow,
        *,
        approval: bool = False,
    ) -> LongRunningAutonomyService:
        guard = LongRunningResourceGuard(
            self.root,
            sample_provider=lambda: {
                "cpu_percent": 1.0,
                "memory_percent": 1.0,
                "disk_free_gb": 100.0,
                "on_ac_power": True,
            },
        )
        return LongRunningAutonomyService(
            self.root,
            workflow=workflow,
            resource_guard=guard,
            diagnostics_service=Diagnostics(approval=approval),
            clock=lambda: NOW,
        )

    def save_lease_job(
        self,
        *,
        cycles: int = 0,
        max_cycles: int = 8,
    ) -> dict:
        store = LongRunningAutonomyStore(self.root)
        return store.save_job(LongRunningJob(
            job_id="longrun-one",
            objective="goal",
            state="QUEUED",
            autonomy_run_id="autonomy-one",
            execution_context={
                "_b54_one_time_auto_approve": True,
                "_b54_repair_id": "repair-one",
                "_b54_approval_lease": {
                    "lease_id": "repair-one",
                    "repair_id": "repair-one",
                    "state": "ACTIVE",
                    "scope": "FULL_AUTONOMY_RUN",
                    "autonomy_run_id": "autonomy-one",
                    "cycles": cycles,
                    "max_cycles": max_cycles,
                },
            },
            metadata={
                "b54_last_repair_id": "repair-one",
                "b54_last_repair_type": "ONE_TIME_APPROVAL",
            },
        ))

    def test_self_repair_creates_scoped_approval_lease(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        store.save_job(LongRunningJob(
            job_id="longrun-repair",
            objective="goal",
            state="WAITING_APPROVAL",
            autonomy_run_id="autonomy-repair",
            last_result={"status": "FULL_AUTONOMY_PAUSED"},
        ))
        repairer = AutonomousSelfRepair(
            self.root,
            long_running_store=store,
        )

        result = repairer.repair_job(
            "longrun-repair",
            {
                "diagnostic_id": "diagnostic-repair",
                "repair_type": "ONE_TIME_APPROVAL",
                "files": ["app/demo.py"],
                "metadata": {"maximum_risk": 3.0},
            },
        )

        saved = store.get_job("longrun-repair")
        lease = saved["execution_context"]["_b54_approval_lease"]
        self.assertTrue(result["success"])
        self.assertEqual(lease["state"], "ACTIVE")
        self.assertEqual(lease["autonomy_run_id"], "autonomy-repair")
        self.assertEqual(lease["authorized_files"], ["app/demo.py"])
        self.assertEqual(
            saved["last_result"]["status"],
            "AUTONOMOUS_REPAIR_QUEUED_WITH_ONE_TIME_APPROVAL",
        )
        self.assertFalse(store.policy()["auto_approve"])

    def test_safe_context_forwards_active_lease(self) -> None:
        service = self.service(Workflow())
        context = service._safe_execution_context({
            "_b54_approval_lease": {"state": "ACTIVE"},
        })
        self.assertTrue(context["auto_approve"])
        self.assertTrue(context["auto_execute"])

    def test_approval_pause_keeps_lease_and_does_not_spend_attempt(self) -> None:
        self.save_lease_job()
        workflow = Workflow(response={
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": "autonomy-one",
            "execution": {"progress_percent": 10.0},
            "errors": [],
        })
        service = self.service(workflow, approval=True)
        job = service.store.get_job("longrun-one")

        result = service._execute_job(job, now=NOW)

        self.assertEqual(result["state"], "SCHEDULED")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(
            result["last_result"]["status"],
            "AUTONOMOUS_APPROVAL_LEASE_CONTINUES",
        )
        self.assertEqual(
            result["execution_context"]["_b54_approval_lease"]["state"],
            "ACTIVE",
        )
        self.assertTrue(workflow.execute_contexts[-1]["auto_approve"])

    def test_completed_run_consumes_lease(self) -> None:
        self.save_lease_job()
        service = self.service(Workflow())
        job = service.store.get_job("longrun-one")

        result = service._execute_job(job, now=NOW)

        self.assertEqual(result["state"], "COMPLETED")
        self.assertNotIn(
            "_b54_approval_lease",
            result["execution_context"],
        )
        self.assertEqual(
            result["metadata"]["b54_approval_lease_state"],
            "CONSUMED_COMPLETED",
        )

    def test_lease_expires_at_bounded_cycle_limit(self) -> None:
        self.save_lease_job(cycles=7, max_cycles=8)
        workflow = Workflow(response={
            "success": True,
            "status": "FULL_AUTONOMY_PAUSED",
            "autonomy_run_id": "autonomy-one",
            "errors": [],
        })
        service = self.service(workflow, approval=True)
        job = service.store.get_job("longrun-one")

        result = service._execute_job(job, now=NOW)

        self.assertEqual(result["state"], "WAITING_APPROVAL")
        self.assertNotIn(
            "_b54_approval_lease",
            result["execution_context"],
        )
        self.assertEqual(
            result["metadata"]["b54_approval_lease_state"],
            "EXPIRED_CYCLE_LIMIT",
        )

    def test_status_reads_live_full_autonomy_progress(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        store.save_job(LongRunningJob(
            job_id="longrun-live",
            objective="goal",
            state="RUNNING",
            autonomy_run_id="autonomy-live",
            last_result={
                "status": "FULL_AUTONOMY_PAUSED",
                "progress_percent": 0.0,
                "diagnostic_category": "APPROVAL_REQUIRED",
            },
        ))
        workflow = Workflow(status_response={
            "success": True,
            "status": "FULL_AUTONOMY_RUNNING",
            "execution": {
                "progress_percent": 37.5,
                "phase": "CAMPAIGN_EXECUTION",
                "updated_at": NOW.isoformat(),
            },
            "errors": [],
        })
        service = self.service(workflow)

        result = service.status("longrun-live")
        monitored = result["job"]["last_result"]

        self.assertEqual(monitored["status"], "FULL_AUTONOMY_RUNNING")
        self.assertEqual(monitored["progress_percent"], 37.5)
        self.assertEqual(monitored["phase"], "CAMPAIGN_EXECUTION")
        self.assertNotIn("diagnostic_category", monitored)

    def test_legacy_flag_is_upgraded_to_persistent_lease(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        store.save_job(LongRunningJob(
            job_id="longrun-legacy",
            objective="goal",
            state="QUEUED",
            autonomy_run_id="autonomy-legacy",
            execution_context={
                "_b54_one_time_auto_approve": True,
                "_b54_repair_id": "repair-legacy",
            },
        ))
        service = self.service(Workflow())
        job = store.get_job("longrun-legacy")

        lease = service._advance_approval_lease(job, now=NOW)

        self.assertEqual(lease["state"], "ACTIVE")
        self.assertEqual(lease["cycles"], 1)
        self.assertIn("_b54_approval_lease", job["execution_context"])

    def test_migration_rearms_only_authorized_active_job(self) -> None:
        store = LongRunningAutonomyStore(self.root)
        store.save_job(LongRunningJob(
            job_id="longrun-authorized",
            objective="goal",
            state="WAITING_APPROVAL",
            autonomy_run_id="autonomy-one",
            metadata={
                "b54_last_repair_id": "repair-one",
                "b54_last_repair_type": "ONE_TIME_APPROVAL",
            },
        ))
        store.save_job(LongRunningJob(
            job_id="longrun-unapproved",
            objective="goal",
            state="WAITING_APPROVAL",
        ))

        result = repair(self.root)

        authorized = store.get_job("longrun-authorized")
        unapproved = store.get_job("longrun-unapproved")
        self.assertEqual(result["rearmed"], 1)
        self.assertEqual(authorized["state"], "QUEUED")
        self.assertEqual(
            authorized["execution_context"]["_b54_approval_lease"]["state"],
            "ACTIVE",
        )
        self.assertEqual(unapproved["state"], "WAITING_APPROVAL")
        self.assertFalse(store.policy()["auto_approve"])

    def test_formatter_reports_live_phase_and_approval_lease(self) -> None:
        text = format_long_running_autonomy_response({
            "status": "LONG_RUNNING_JOB_STATUS",
            "job": {
                "job_id": "longrun-one",
                "state": "RUNNING",
                "last_result": {
                    "status": "FULL_AUTONOMY_RUNNING",
                    "progress_percent": 25.0,
                    "phase": "CAMPAIGN_EXECUTION",
                    "approval_lease_state": "ACTIVE",
                },
            },
        })
        self.assertIn("Faza wykonania: CAMPAIGN_EXECUTION", text)
        self.assertIn("Jednorazowa zgoda: ACTIVE", text)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_command_router import BrainCommandRouter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
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
from app.ai.software_engineer.software_engineer_long_running_formatter import (
    format_long_running_autonomy_response,
)
from app.ai.software_engineer.software_engineer_long_running_router import (
    SoftwareEngineerLongRunningRouter,
)
from app.gui.command_safety import is_read_only_learning_command


JOB_ID = "longrun-final-monitoring-123"


class B53FinalControlMonitoringTests(unittest.TestCase):

    def _controller(self, service: object) -> SimpleNamespace:
        return SimpleNamespace(
            project_root=Path("."),
            long_running_autonomy_service=service,
            _normalize=AutonomousSoftwareEngineerController._normalize,
        )

    def _route(
        self,
        command: str,
        *,
        service: object | None = None,
        context: dict | None = None,
        objective: str | None = None,
    ) -> tuple[dict, object]:
        service = service or MagicMock()
        controller = self._controller(service)
        result = SoftwareEngineerLongRunningRouter().try_handle(
            controller,
            command=command,
            objective=objective or command,
            context=dict(context or {}),
        )
        self.assertIsNotNone(result)
        return result, service

    def test_controller_accepts_exact_job_status_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                f"Pokaż status zadania długotrwałego {JOB_ID}"
            )
        )

    def test_controller_accepts_plain_job_status_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                f"Pokaż status zadania {JOB_ID}"
            )
        )

    def test_controller_accepts_all_jobs_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Pokaż wszystkie zadania"
            )
        )

    def test_controller_accepts_clear_completed_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Usuń zakończone zadania"
            )
        )

    def test_brain_routes_exact_job_status_command(self) -> None:
        brain = SimpleNamespace(
            cognitive=MagicMock(),
            software_engineer_controller=SimpleNamespace(
                can_handle=AutonomousSoftwareEngineerController.can_handle,
            ),
        )
        thought = BrainCommandRouter().think(
            brain,
            f"Pokaż status zadania długotrwałego {JOB_ID}",
        )
        self.assertEqual(
            thought["handler"],
            "autonomous_software_engineer",
        )

    def test_router_routes_exact_job_status(self) -> None:
        service = MagicMock()
        service.status.return_value = {
            "success": True,
            "status": "LONG_RUNNING_JOB_STATUS",
            "operation": "long_running_autonomy",
        }
        result, _ = self._route(
            f"Pokaż status zadania długotrwałego {JOB_ID}",
            service=service,
        )
        self.assertEqual(result["status"], "LONG_RUNNING_JOB_STATUS")
        service.status.assert_called_once_with(JOB_ID)

    def test_router_routes_plain_job_status(self) -> None:
        service = MagicMock()
        service.status.return_value = {
            "success": True,
            "status": "LONG_RUNNING_JOB_STATUS",
            "operation": "long_running_autonomy",
        }
        self._route(
            f"Pokaż status zadania {JOB_ID}",
            service=service,
        )
        service.status.assert_called_once_with(JOB_ID)

    def test_router_routes_all_jobs_list(self) -> None:
        service = MagicMock()
        service.recent.return_value = {
            "success": True,
            "status": "LONG_RUNNING_AUTONOMY_RECENT",
            "operation": "long_running_autonomy",
        }
        self._route("Pokaż wszystkie zadania", service=service)
        service.recent.assert_called_once_with(limit=20)

    def test_router_routes_queue_command(self) -> None:
        service = MagicMock()
        service.recent.return_value = {
            "success": True,
            "status": "LONG_RUNNING_AUTONOMY_RECENT",
            "operation": "long_running_autonomy",
        }
        self._route("Pokaż kolejkę autonomii", service=service)
        service.recent.assert_called_once_with(limit=20)

    def test_router_routes_plain_pause_job(self) -> None:
        service = MagicMock()
        service.pause_job.return_value = {"status": "LONG_RUNNING_JOB_PAUSED"}
        self._route(f"Wstrzymaj zadanie {JOB_ID}", service=service)
        service.pause_job.assert_called_once_with(JOB_ID)

    def test_router_routes_plain_resume_job(self) -> None:
        service = MagicMock()
        service.resume_job.return_value = {"status": "LONG_RUNNING_JOB_RESUMED"}
        self._route(f"Wznów zadanie {JOB_ID}", service=service)
        service.resume_job.assert_called_once_with(JOB_ID)

    def test_router_routes_plain_cancel_job(self) -> None:
        service = MagicMock()
        service.cancel_job.return_value = {"status": "LONG_RUNNING_JOB_CANCELLED"}
        self._route(f"Anuluj zadanie {JOB_ID}", service=service)
        service.cancel_job.assert_called_once_with(JOB_ID)

    def test_router_routes_run_now_job(self) -> None:
        service = MagicMock()
        service.run_job_now.return_value = {"status": "LONG_RUNNING_TICK_COMPLETED"}
        self._route(f"Wykonaj teraz zadanie {JOB_ID}", service=service)
        service.run_job_now.assert_called_once_with(JOB_ID)

    def test_router_routes_delete_terminal_job(self) -> None:
        service = MagicMock()
        service.delete_job.return_value = {"status": "LONG_RUNNING_JOB_DELETED"}
        self._route(f"Usuń zadanie {JOB_ID}", service=service)
        service.delete_job.assert_called_once_with(JOB_ID)

    def test_router_routes_clear_completed_jobs(self) -> None:
        service = MagicMock()
        service.clear_terminal_jobs.return_value = {
            "status": "LONG_RUNNING_TERMINAL_JOBS_CLEARED"
        }
        self._route("Usuń zakończone zadania", service=service)
        service.clear_terminal_jobs.assert_called_once_with()

    def test_router_recognizes_job_id_without_long_phrase(self) -> None:
        service = MagicMock()
        service.cancel_job.return_value = {"status": "LONG_RUNNING_JOB_CANCELLED"}
        result, _ = self._route(
            f"Anuluj zadanie {JOB_ID}",
            service=service,
        )
        self.assertEqual(result["status"], "LONG_RUNNING_JOB_CANCELLED")

    def test_router_requires_job_id_for_plain_job_action(self) -> None:
        result, _ = self._route("Anuluj zadanie długotrwałe")
        self.assertEqual(result["status"], "LONG_RUNNING_JOB_ID_REQUIRED")

    def test_router_cleans_enqueue_objective_prefix(self) -> None:
        service = MagicMock()
        service.enqueue.return_value = {"status": "LONG_RUNNING_JOB_ENQUEUED"}
        self._route(
            "Zaplanuj długotrwałą autonomię: utwórz moduł demo",
            service=service,
            objective="Zaplanuj: utwórz moduł demo",
        )
        objective = service.enqueue.call_args.args[0]
        self.assertEqual(objective, "utwórz moduł demo")

    def test_router_parses_every_hour_schedule(self) -> None:
        value = SoftwareEngineerLongRunningRouter._schedule_from_command(
            "Zaplanuj długotrwałą autonomię co godzinę: test"
        )
        self.assertEqual(value["interval_minutes"], 60)

    def test_router_parses_every_minute_schedule(self) -> None:
        value = SoftwareEngineerLongRunningRouter._schedule_from_command(
            "Zaplanuj długotrwałą autonomię co minutę: test"
        )
        self.assertEqual(value["interval_minutes"], 1)

    def test_store_deletes_single_job(self) -> None:
        with TemporaryDirectory() as directory:
            store = LongRunningAutonomyStore(directory)
            job = LongRunningJob(objective="done", state="COMPLETED")
            store.save_job(job)
            removed = store.delete_job(job.job_id)
            self.assertEqual(removed["job_id"], job.job_id)
            self.assertIsNone(store.get_job(job.job_id))

    def test_store_deletes_only_selected_states(self) -> None:
        with TemporaryDirectory() as directory:
            store = LongRunningAutonomyStore(directory)
            completed = LongRunningJob(objective="done", state="COMPLETED")
            failed = LongRunningJob(objective="failed", state="FAILED")
            queued = LongRunningJob(objective="queued", state="QUEUED")
            for job in (completed, failed, queued):
                store.save_job(job)
            removed = store.delete_jobs_by_state({"COMPLETED", "FAILED"})
            self.assertEqual(len(removed), 2)
            self.assertIsNotNone(store.get_job(queued.job_id))

    def test_service_deletes_terminal_job(self) -> None:
        with TemporaryDirectory() as directory:
            store = LongRunningAutonomyStore(directory)
            job = LongRunningJob(objective="done", state="COMPLETED")
            store.save_job(job)
            service = LongRunningAutonomyService(
                directory,
                workflow=MagicMock(),
                store=store,
            )
            result = service.delete_job(job.job_id)
            self.assertTrue(result["success"])
            self.assertEqual(result["removed"], 1)

    def test_service_blocks_delete_of_active_job(self) -> None:
        with TemporaryDirectory() as directory:
            store = LongRunningAutonomyStore(directory)
            job = LongRunningJob(objective="active", state="RUNNING")
            store.save_job(job)
            service = LongRunningAutonomyService(
                directory,
                workflow=MagicMock(),
                store=store,
            )
            result = service.delete_job(job.job_id)
            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "LONG_RUNNING_JOB_DELETE_BLOCKED")
            self.assertIsNotNone(store.get_job(job.job_id))

    def test_service_clears_terminal_jobs_only(self) -> None:
        with TemporaryDirectory() as directory:
            store = LongRunningAutonomyStore(directory)
            for state in ("COMPLETED", "FAILED", "CANCELLED", "QUEUED"):
                store.save_job(LongRunningJob(objective=state, state=state))
            service = LongRunningAutonomyService(
                directory,
                workflow=MagicMock(),
                store=store,
            )
            result = service.clear_terminal_jobs()
            self.assertEqual(result["removed"], 3)
            remaining = store.list_jobs(limit=20)
            self.assertEqual([job["state"] for job in remaining], ["QUEUED"])

    def test_service_recent_reports_counts(self) -> None:
        with TemporaryDirectory() as directory:
            store = LongRunningAutonomyStore(directory)
            store.save_job(LongRunningJob(objective="one", state="QUEUED"))
            store.save_job(LongRunningJob(objective="two", state="COMPLETED"))
            service = LongRunningAutonomyService(
                directory,
                workflow=MagicMock(),
                store=store,
            )
            result = service.recent(limit=20)
            self.assertEqual(result["counts"]["QUEUED"], 1)
            self.assertEqual(result["counts"]["COMPLETED"], 1)

    def test_formatter_lists_queue_jobs(self) -> None:
        text = format_long_running_autonomy_response({
            "status": "LONG_RUNNING_AUTONOMY_RECENT",
            "jobs": [
                {
                    "job_id": JOB_ID,
                    "state": "WAITING_RESOURCES",
                    "priority": 50,
                    "attempts": 0,
                    "max_attempts": 3,
                    "next_run_at": "2026-07-16T20:00:00+00:00",
                }
            ],
            "counts": {"WAITING_RESOURCES": 1},
        })
        self.assertIn(JOB_ID, text)
        self.assertIn("WAITING_RESOURCES", text)
        self.assertIn("Stany:", text)

    def test_formatter_reports_detailed_job_monitoring(self) -> None:
        text = format_long_running_autonomy_response({
            "status": "LONG_RUNNING_JOB_STATUS",
            "job": {
                "job_id": JOB_ID,
                "state": "RUNNING",
                "priority": 80,
                "attempts": 1,
                "max_attempts": 3,
                "objective": "test",
                "schedule": {"type": "daily"},
                "autonomy_run_id": "autonomy-test",
                "heartbeat_at": "now",
                "last_result": {
                    "status": "FULL_AUTONOMY_RUNNING",
                    "progress_percent": 50,
                },
                "run_history": [{"status": "COMPLETED"}],
            },
        })
        self.assertIn("Harmonogram: daily", text)
        self.assertIn("Autonomy Run ID: autonomy-test", text)
        self.assertIn("Postęp autonomii: 50%", text)
        self.assertIn("Historia wykonań: 1", text)

    def test_job_status_is_read_only(self) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                f"Pokaż status zadania długotrwałego {JOB_ID}"
            )
        )

    def test_all_jobs_list_is_read_only(self) -> None:
        self.assertTrue(
            is_read_only_learning_command("Pokaż wszystkie zadania")
        )

    def test_clear_completed_requires_confirmation(self) -> None:
        self.assertFalse(
            is_read_only_learning_command("Usuń zakończone zadania")
        )

    def test_delete_job_requires_confirmation(self) -> None:
        self.assertFalse(
            is_read_only_learning_command(f"Usuń zadanie {JOB_ID}")
        )


if __name__ == "__main__":
    unittest.main()

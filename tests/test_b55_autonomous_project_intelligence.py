"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.project_intelligence_models import (
    ProjectIntelligencePolicy,
    ProjectOpportunity,
)
from app.ai.software_engineer.project_intelligence_ranker import (
    ProjectOpportunityRanker,
)
from app.ai.software_engineer.project_intelligence_service import (
    ProjectIntelligenceService,
    bootstrap_project_intelligence,
)
from app.ai.software_engineer.project_intelligence_scanner import (
    ProjectOpportunityScanner,
)
from app.ai.software_engineer.project_intelligence_store import (
    ProjectIntelligenceStore,
)
from app.ai.software_engineer.software_engineer_project_intelligence_formatter import (
    format_project_intelligence_response,
)
from app.ai.software_engineer.software_engineer_project_intelligence_router import (
    SoftwareEngineerProjectIntelligenceRouter,
)
from app.gui.command_safety import (
    is_read_only_learning_command,
)


def opportunity(
    *,
    opportunity_id: str = "opportunity-aaaaaaaaaaaaaaaa",
    fingerprint: str = "fingerprint-a",
    status: str = "PENDING",
    risk: float = 20.0,
    score: float = 50.0,
    confidence: float = 0.8,
) -> dict:
    return ProjectOpportunity(
        opportunity_id=opportunity_id,
        title="Popraw walidację modułu",
        objective="Bezpiecznie popraw walidację app/demo.py.",
        target="app/demo.py",
        fingerprint=fingerprint,
        value_score=50.0,
        risk_score=risk,
        effort_score=5.0,
        confidence=confidence,
        final_score=score,
        status=status,
    ).to_dict()


class B55ScannerTests(unittest.TestCase):

    def test_scanner_detects_syntax_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "app" / "broken.py").write_text(
                "def broken(:\n    pass\n",
                encoding="utf-8",
            )
            cycle = ProjectOpportunityScanner(root).run_cycle()
        candidates = cycle["prioritization"]["candidates"]
        self.assertEqual(
            candidates[0]["task"]["metadata"]["issue_type"],
            "SYNTAX_ERROR",
        )

    def test_scanner_detects_large_module(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            source = "\n".join(
                ["VALUE = 1"] * 700
            )
            (root / "app" / "large.py").write_text(
                source,
                encoding="utf-8",
            )
            cycle = ProjectOpportunityScanner(root).run_cycle()
        issue_types = {
            item["task"]["metadata"]["issue_type"]
            for item in cycle["prioritization"]["candidates"]
        }
        self.assertIn("LARGE_MODULE", issue_types)

    def test_scanner_ignores_data_directory(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "data").mkdir()
            (root / "data" / "broken.py").write_text(
                "def broken(:\n",
                encoding="utf-8",
            )
            cycle = ProjectOpportunityScanner(root).run_cycle()
        self.assertEqual(cycle["files_scanned"], 0)

    def test_scanner_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            for index in range(80):
                (root / "app" / f"m{index}.py").write_text(
                    "VALUE = 1\n",
                    encoding="utf-8",
                )
            cycle = ProjectOpportunityScanner(
                root,
                max_files=50,
            ).run_cycle()
        self.assertEqual(cycle["files_scanned"], 50)

    def test_scanner_returns_safe_generation_decision(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            lines = [
                "def long_function():",
                *["    value = 1" for _ in range(90)],
                "    return value",
            ]
            (root / "app" / "long.py").write_text(
                "\n".join(lines),
                encoding="utf-8",
            )
            cycle = ProjectOpportunityScanner(root).run_cycle()
        candidate = cycle["prioritization"]["candidates"][0]
        self.assertEqual(
            candidate["decision"],
            "READY_FOR_SAFE_GENERATION",
        )


class B55ModelsStoreTests(unittest.TestCase):

    def test_opportunity_round_trip(self) -> None:
        value = opportunity()
        restored = ProjectOpportunity.from_dict(value)
        self.assertEqual(restored.opportunity_id, value["opportunity_id"])
        self.assertEqual(restored.status, "PENDING")

    def test_policy_never_enables_auto_approve(self) -> None:
        policy = ProjectIntelligencePolicy.from_dict({
            "auto_approve": True,
            "max_active_jobs": 99,
            "scan_interval_seconds": 1,
        })
        self.assertFalse(policy.auto_approve)
        self.assertEqual(policy.max_active_jobs, 3)
        self.assertEqual(policy.scan_interval_seconds, 30.0)

    def test_store_saves_and_reads_opportunity(self) -> None:
        with TemporaryDirectory() as directory:
            store = ProjectIntelligenceStore(directory)
            saved = store.save_opportunity(opportunity())
            loaded = store.get_opportunity(saved["opportunity_id"])
        self.assertEqual(loaded["fingerprint"], "fingerprint-a")

    def test_store_deduplicates_by_fingerprint(self) -> None:
        with TemporaryDirectory() as directory:
            store = ProjectIntelligenceStore(directory)
            first = store.upsert_by_fingerprint(opportunity())
            second_value = opportunity(
                opportunity_id="opportunity-bbbbbbbbbbbbbbbb",
            )
            second_value["title"] = "Nowszy tytuł"
            second = store.upsert_by_fingerprint(second_value)
            items = store.list_opportunities(limit=100)
        self.assertEqual(first["opportunity_id"], second["opportunity_id"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Nowszy tytuł")

    def test_store_updates_status(self) -> None:
        with TemporaryDirectory() as directory:
            store = ProjectIntelligenceStore(directory)
            item = store.save_opportunity(opportunity())
            updated = store.update_opportunity(
                item["opportunity_id"],
                {"status": "RUNNING", "attempts": 1},
            )
        self.assertEqual(updated["status"], "RUNNING")
        self.assertEqual(updated["attempts"], 1)

    def test_store_records_bounded_cycles(self) -> None:
        with TemporaryDirectory() as directory:
            store = ProjectIntelligenceStore(directory, max_cycles=50)
            for index in range(70):
                store.record_cycle({
                    "status": f"CYCLE-{index}",
                    "success": True,
                })
            cycles = store.cycles(limit=100)
        self.assertEqual(len(cycles), 50)
        self.assertEqual(cycles[0]["status"], "CYCLE-69")

    def test_store_policy_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            store = ProjectIntelligenceStore(directory)
            policy = store.update_policy({
                "max_risk": 999,
                "min_score": -1,
                "auto_approve": True,
            })
        self.assertEqual(policy["max_risk"], 100.0)
        self.assertEqual(policy["min_score"], 0.0)
        self.assertFalse(policy["auto_approve"])

    def test_store_summary_counts_states(self) -> None:
        with TemporaryDirectory() as directory:
            store = ProjectIntelligenceStore(directory)
            store.save_opportunity(opportunity(status="PENDING"))
            store.save_opportunity(opportunity(
                opportunity_id="opportunity-bbbbbbbbbbbbbbbb",
                fingerprint="fingerprint-b",
                status="COMPLETED",
            ))
            summary = store.summary()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["completed"], 1)


class B55RankerTests(unittest.TestCase):

    def setUp(self) -> None:
        self.ranker = ProjectOpportunityRanker()

    def test_ranker_prefers_higher_value_lower_risk(self) -> None:
        low = opportunity(
            opportunity_id="opportunity-1111111111111111",
            fingerprint="low",
            risk=50,
        )
        low["value_score"] = 20
        high = opportunity(
            opportunity_id="opportunity-2222222222222222",
            fingerprint="high",
            risk=10,
        )
        high["value_score"] = 60
        selected = self.ranker.select_best(
            [low, high],
            min_score=0,
            max_risk=100,
            min_confidence=0,
        )
        self.assertEqual(selected["fingerprint"], "high")

    def test_ranker_blocks_high_risk(self) -> None:
        selected = self.ranker.select_best(
            [opportunity(risk=90)],
            min_score=0,
            max_risk=65,
            min_confidence=0,
        )
        self.assertIsNone(selected)

    def test_ranker_blocks_low_confidence(self) -> None:
        selected = self.ranker.select_best(
            [opportunity(confidence=0.1)],
            min_score=0,
            max_risk=100,
            min_confidence=0.3,
        )
        self.assertIsNone(selected)

    def test_ranker_skips_active_and_terminal(self) -> None:
        values = [
            opportunity(status="RUNNING"),
            opportunity(
                opportunity_id="opportunity-2222222222222222",
                fingerprint="done",
                status="COMPLETED",
            ),
        ]
        selected = self.ranker.select_best(
            values,
            min_score=0,
            max_risk=100,
            min_confidence=0,
        )
        self.assertIsNone(selected)

    def test_ranker_adds_explanation(self) -> None:
        scored = self.ranker.score(opportunity())
        self.assertIn("ranking", scored)
        self.assertIn("risk", scored["ranking"])


class B55ServiceTests(unittest.TestCase):

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "app").mkdir()
        (self.root / "app" / "demo.py").write_text(
            "def demo():\n    return 1\n",
            encoding="utf-8",
        )
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_demo.py").write_text(
            "from app.demo import demo\n",
            encoding="utf-8",
        )
        self.intelligence = MagicMock()
        self.long_running = MagicMock()
        self.long_running.store.get_job.return_value = None
        self.long_running.enqueue.return_value = {
            "success": True,
            "status": "LONG_RUNNING_JOB_ENQUEUED",
            "job_id": "longrun-123",
            "job": {
                "job_id": "longrun-123",
                "state": "QUEUED",
            },
        }
        self.store = ProjectIntelligenceStore(self.root)
        self.service = ProjectIntelligenceService(
            self.root,
            intelligence=self.intelligence,
            long_running_service=self.long_running,
            store=self.store,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def cycle(self, *, target: str = "app/demo.py") -> dict:
        return {
            "success": True,
            "prioritization": {
                "candidates": [
                    {
                        "task": {
                            "title": "Popraw walidację",
                            "description": "Dodaj bezpieczną walidację.",
                            "target": target,
                            "severity": "HIGH",
                            "priority_score": 60,
                            "metadata": {
                                "issue_type": "VALIDATION",
                                "estimated_effort": 5,
                                "confidence": 0.9,
                            },
                        },
                        "predicted_risk": 10,
                        "value_score": 55,
                        "effort_score": 5,
                        "final_score": 80,
                        "decision": "READY_FOR_SAFE_GENERATION",
                    }
                ]
            },
        }

    def test_scan_creates_persistent_backlog(self) -> None:
        self.intelligence.run_cycle.return_value = self.cycle()
        result = self.service.scan_project()
        self.assertTrue(result["success"])
        self.assertEqual(result["created"], 1)
        self.assertEqual(self.store.summary()["total"], 1)

    def test_scan_deduplicates_repeated_finding(self) -> None:
        self.intelligence.run_cycle.return_value = self.cycle()
        self.service.scan_project()
        result = self.service.scan_project()
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(self.store.summary()["total"], 1)

    def test_scan_rejects_target_outside_project(self) -> None:
        self.intelligence.run_cycle.return_value = self.cycle(
            target="../outside.py"
        )
        result = self.service.scan_project()
        self.assertEqual(result["scanned"], 0)

    def test_select_best_uses_policy(self) -> None:
        self.store.save_opportunity(opportunity())
        result = self.service.select_best()
        self.assertEqual(
            result["status"],
            "PROJECT_INTELLIGENCE_BEST_SELECTED",
        )

    def test_dispatch_requires_explicit_force_by_default(self) -> None:
        self.store.save_opportunity(opportunity())
        result = self.service.dispatch_best(force=False)
        self.assertEqual(
            result["status"],
            "PROJECT_INTELLIGENCE_AUTO_DISPATCH_DISABLED",
        )
        self.long_running.enqueue.assert_not_called()

    def test_explicit_dispatch_never_auto_approves(self) -> None:
        self.store.save_opportunity(opportunity())
        result = self.service.dispatch_best(force=True)
        self.assertTrue(result["success"])
        context = self.long_running.enqueue.call_args.kwargs["context"]
        self.assertFalse(context["auto_approve"])
        self.assertTrue(context["auto_rollback"])
        self.assertEqual(
            context["autonomy_targets"][0],
            "app/demo.py",
        )
        self.assertIn(
            "tests/test_demo.py",
            context["autonomy_targets"],
        )
        self.assertEqual(
            context["autonomy_metadata"]["planning_mode"],
            "project_intelligence_scoped",
        )
        saved = self.store.get_opportunity(
            "opportunity-aaaaaaaaaaaaaaaa"
        )
        self.assertEqual(saved["status"], "DISPATCHED")
        self.assertEqual(saved["job_id"], "longrun-123")

    def test_active_limit_blocks_second_dispatch(self) -> None:
        self.store.save_opportunity(opportunity(status="RUNNING"))
        self.store.save_opportunity(opportunity(
            opportunity_id="opportunity-bbbbbbbbbbbbbbbb",
            fingerprint="fingerprint-b",
        ))
        result = self.service.dispatch_best(force=True)
        self.assertEqual(
            result["status"],
            "PROJECT_INTELLIGENCE_ACTIVE_LIMIT",
        )

    def test_reconcile_marks_completed(self) -> None:
        item = opportunity(status="DISPATCHED")
        item["job_id"] = "longrun-123"
        self.store.save_opportunity(item)
        self.long_running.store.get_job.return_value = {
            "job_id": "longrun-123",
            "state": "COMPLETED",
            "attempts": 1,
            "completed_at": "2026-01-01T00:00:00+00:00",
        }
        result = self.service.reconcile()
        saved = self.store.get_opportunity(item["opportunity_id"])
        self.assertEqual(result["reconciled"], 1)
        self.assertEqual(saved["status"], "COMPLETED")

    def test_reconcile_propagates_waiting_approval(self) -> None:
        item = opportunity(status="DISPATCHED")
        item["job_id"] = "longrun-123"
        self.store.save_opportunity(item)
        self.long_running.store.get_job.return_value = {
            "job_id": "longrun-123",
            "state": "WAITING_APPROVAL",
            "attempts": 1,
        }
        self.service.reconcile()
        saved = self.store.get_opportunity(item["opportunity_id"])
        self.assertEqual(saved["status"], "WAITING_APPROVAL")

    def test_run_cycle_does_not_dispatch_when_disabled(self) -> None:
        self.intelligence.run_cycle.return_value = self.cycle()
        result = self.service.run_cycle()
        self.assertTrue(result["success"])
        self.long_running.enqueue.assert_not_called()

    def test_run_cycle_can_dispatch_explicitly(self) -> None:
        self.intelligence.run_cycle.return_value = self.cycle()
        result = self.service.run_cycle(dispatch=True)
        self.assertTrue(result["success"])
        self.long_running.enqueue.assert_called_once()

    def test_update_policy_preserves_auto_approve_false(self) -> None:
        result = self.service.update_policy({
            "auto_dispatch": True,
            "auto_approve": True,
        })
        self.assertTrue(result["policy"]["auto_dispatch"])
        self.assertFalse(result["policy"]["auto_approve"])

    def test_reject_pending_opportunity(self) -> None:
        self.store.save_opportunity(opportunity())
        result = self.service.reject(
            "opportunity-aaaaaaaaaaaaaaaa"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["selected"]["status"], "REJECTED")

    def test_reject_active_opportunity_is_blocked(self) -> None:
        self.store.save_opportunity(opportunity(status="RUNNING"))
        result = self.service.reject(
            "opportunity-aaaaaaaaaaaaaaaa"
        )
        self.assertFalse(result["success"])

    def test_start_background_starts_long_running_supervisor(self) -> None:
        result = self.service.start_background()
        self.assertTrue(result["success"])
        self.long_running.start_background.assert_called_once()
        self.assertTrue(self.store.policy()["auto_dispatch"])
        self.assertFalse(self.store.policy()["auto_approve"])
        self.service.stop_background()

    def test_start_if_enabled_does_not_start_when_disabled(self) -> None:
        result = self.service.start_if_enabled()
        self.assertEqual(
            result["status"],
            "PROJECT_INTELLIGENCE_SUPERVISOR_DISABLED",
        )


class B55RoutingFormattingTests(unittest.TestCase):

    def setUp(self) -> None:
        self.router = SoftwareEngineerProjectIntelligenceRouter()
        self.service = MagicMock()
        self.controller = SimpleNamespace(
            project_root=Path("C:/JarvisAI"),
            project_intelligence_service=self.service,
            _normalize=AutonomousSoftwareEngineerController._normalize,
        )
        self.service.start_if_enabled.return_value = {
            "success": True,
        }

    def test_controller_accepts_status_command(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "Pokaż status inteligencji projektu"
            )
        )

    def test_router_routes_status(self) -> None:
        self.service.status.return_value = {"status": "OK"}
        result = self.router.try_handle(
            self.controller,
            command="Pokaż status inteligencji projektu",
            objective="",
            context={},
        )
        self.assertEqual(result["status"], "OK")
        self.service.status.assert_called_once()

    def test_router_routes_scan(self) -> None:
        self.service.scan_project.return_value = {"status": "SCAN"}
        result = self.router.try_handle(
            self.controller,
            command="Skanuj projekt i zbuduj backlog",
            objective="",
            context={},
        )
        self.assertEqual(result["status"], "SCAN")

    def test_router_routes_dispatch(self) -> None:
        self.service.dispatch_best.return_value = {"status": "DISPATCH"}
        result = self.router.try_handle(
            self.controller,
            command="Uruchom najlepsze zadanie rozwoju",
            objective="",
            context={},
        )
        self.assertEqual(result["status"], "DISPATCH")
        self.service.dispatch_best.assert_called_once_with(force=True)

    def test_router_parses_opportunity_id(self) -> None:
        self.service.opportunity.return_value = {"status": "ITEM"}
        item_id = "opportunity-abcdefabcdefabcd"
        self.router.try_handle(
            self.controller,
            command=f"Pokaż status zadania rozwoju {item_id}",
            objective="",
            context={},
        )
        self.service.opportunity.assert_called_once_with(item_id)

    def test_status_and_backlog_are_read_only(self) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż status inteligencji projektu"
            )
        )
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż backlog rozwoju"
            )
        )
        self.assertTrue(
            is_read_only_learning_command(
                "Skanuj projekt i zbuduj backlog"
            )
        )

    def test_mutating_commands_require_confirmation(self) -> None:
        self.assertFalse(
            is_read_only_learning_command(
                "Uruchom autonomiczny rozwój projektu"
            )
        )
        self.assertFalse(
            is_read_only_learning_command(
                "Uruchom najlepsze zadanie rozwoju"
            )
        )

    def test_formatter_reports_policy_and_selected(self) -> None:
        text = format_project_intelligence_response({
            "status": "PROJECT_INTELLIGENCE_STATUS",
            "summary": {
                "total": 1,
                "pending": 1,
                "active": 0,
                "completed": 0,
                "failed": 0,
            },
            "runtime": {
                "enabled": True,
                "cycles_completed": 2,
            },
            "policy": {
                "min_score": 25,
                "max_risk": 65,
                "max_active_jobs": 1,
                "auto_dispatch": False,
            },
            "selected": opportunity(),
            "report_path": "data/project_intelligence.json",
        })
        self.assertIn("Nadzorca B55: AKTYWNY", text)
        self.assertIn("auto-approve NIE", text)
        self.assertIn("Najlepsze zadanie", text)

    def test_brain_formatter_routes_project_intelligence(self) -> None:
        formatter = BrainResponseFormatter()
        text = formatter._format_software_engineer_response({
            "success": True,
            "status": "PROJECT_INTELLIGENCE_STATUS",
            "operation": "project_intelligence",
            "summary": {},
            "runtime": {},
            "policy": {},
        })
        self.assertIn("Inteligencja projektu", text)

    def test_bootstrap_reuses_existing_service(self) -> None:
        result = bootstrap_project_intelligence(self.controller)
        self.assertIs(result, self.service)
        self.service.start_if_enabled.assert_called()


if __name__ == "__main__":
    unittest.main()

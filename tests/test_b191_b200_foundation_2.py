from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.ai.software_engineer.autodev_safe_preview import (
    prepare_safe_autodev_runtime,
)
from app.ai.software_engineer.project_intelligence_service import (
    ProjectIntelligenceService,
)
from app.gui.active_resolution_priority import active_resolution_priority_thought
from app.gui.confirmed_calendar_execution import execute_confirmed_calendar_plan
from app.jarvis_experience.isolation import ClientIsolationPolicy
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from tests.test_b186_b190_gmail_live_workflow import AssistantStub, FakeOnline


class _Assistant:
    def __init__(self, service):
        self.natural_actions = service


class _Window:
    def __init__(self, service):
        self.assistant = _Assistant(service)
        self.brain = SimpleNamespace(
            execute=lambda _thought: (_ for _ in ()).throw(
                AssertionError("Exact Gmail route must not use global Brain.")
            )
        )



class _LongRunning:
    def __init__(self):
        self.calls = []

    def enqueue(self, objective, *, context=None):
        self.calls.append((objective, dict(context or {})))
        return {
            "success": True,
            "job_id": "job-safe-preview",
            "job": {"job_id": "job-safe-preview"},
        }


class B191B200Foundation2Tests(unittest.TestCase):
    def test_stale_sent_flag_is_repaired_from_live_gmail_draft(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = NaturalActionService(directory, online=online)
            service.handle("Znajdź ostatnią wiadomość od anna@example.com")
            reply = service.plan("Przygotuj odpowiedź: Dziękuję za wiadomość")
            PlannedNaturalActionExecutor.execute(AssistantStub(service), reply)

            path = Path(directory) / "data/online_assistant/gmail_live_workflow.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["last_draft"].update({
                "sent": True,
                "sent_message_id": "fake-test-receipt",
            })
            path.write_text(json.dumps(data), encoding="utf-8")

            online.provider.get_gmail_draft = lambda draft_id: {
                "draft_id": draft_id,
                "message_id": "draft-message-1",
                "thread_id": "t1",
                "recipient": "anna@example.com",
                "recipient_email": "anna@example.com",
                "subject": "Re: Faktura lipiec",
                "body": "Dziękuję za wiadomość",
            }
            online.provider.list_gmail_drafts = lambda max_results=20: []
            recreated = NaturalActionService(directory, online=online)
            window = _Window(recreated)
            thought = active_resolution_priority_thought(
                window, "Wyślij tę odpowiedź"
            )
            self.assertIsNotNone(thought)
            self.assertTrue(thought["requires_confirmation"])
            self.assertEqual(
                thought["natural_slots"]["draft_id"], "draft-reply-1"
            )
            response = execute_confirmed_calendar_plan(window, thought)

        self.assertEqual(online.provider.sent, ["draft-reply-1"])
        self.assertIn("sprawdzony w Gmail", response)

    def test_live_draft_recovery_rejects_ambiguous_unrelated_drafts(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            center = NaturalActionService(directory, online=online).runtime.gmail_live.center
            online.provider.get_gmail_draft = lambda _draft_id: {}
            online.provider.list_gmail_drafts = lambda max_results=20: [
                {"draft_id": "a", "subject": "A", "recipient": "a@example.com"},
                {"draft_id": "b", "subject": "B", "recipient": "b@example.com"},
            ]
            self.assertEqual(center.resolve_sendable_draft(), {})

    def test_real_client_runtime_delegates_planning_off_ui_thread(self) -> None:
        root = Path(__file__).resolve().parents[1]
        runtime = (root / "app/gui/client_command_runtime.py").read_text(
            encoding="utf-8"
        )
        worker = (root / "app/gui/client_background_commands.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('getattr(self, "_client_async_enabled", False)', runtime)
        self.assertIn("self._client_background().plan(value)", runtime)
        self.assertIn("QThreadPool", worker)
        self.assertIn("setMaxThreadCount(1)", worker)
        self.assertIn("@Slot(object, object)", worker)
        self.assertNotIn("lambda result, current=job", worker)

    def test_stage_prefix_does_not_hide_natural_result(self) -> None:
        self.assertEqual(
            ClientIsolationPolicy.sanitize_text("B195: Podgląd zmiany jest gotowy."),
            "Podgląd zmiany jest gotowy.",
        )
        long_message = "Treść wiadomości " + "x" * 1800
        self.assertGreater(
            len(ClientIsolationPolicy.sanitize_action_result(long_message)), 1500
        )

    def test_safe_autodev_bootstrap_enables_preview_not_auto_approval(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir(parents=True)
            (root / "config/b195_autodev_safe_preview.json").write_text(
                json.dumps({"enabled": True, "scan_interval_seconds": 600}),
                encoding="utf-8",
            )
            data_dir = root / "data/autodev"
            data_dir.mkdir(parents=True)
            state = {
                "version": 1,
                "opportunities": {},
                "order": [],
                "cycles": [],
                "runtime": {"enabled": False, "running": True},
                "policy": {"auto_dispatch": False, "auto_approve": True},
            }
            (data_dir / "project_intelligence.json").write_text(
                json.dumps(state), encoding="utf-8"
            )
            (data_dir / ".project_intelligence.json.orphan.tmp").write_text(
                "orphan", encoding="utf-8"
            )
            result = prepare_safe_autodev_runtime(root)
            repaired = json.loads(
                (data_dir / "project_intelligence.json").read_text(encoding="utf-8")
            )
        self.assertEqual(result["status"], "SAFE_AUTODEV_PREVIEW_READY")
        self.assertTrue(repaired["runtime"]["enabled"])
        self.assertFalse(repaired["runtime"]["running"])
        self.assertTrue(repaired["policy"]["auto_dispatch"])
        self.assertFalse(repaired["policy"]["auto_approve"])
        self.assertEqual(repaired["policy"]["max_active_jobs"], 1)

    def test_project_intelligence_dispatches_one_approval_gated_preview(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            (root / "tests").mkdir()
            (root / "app/example.py").write_text("def value():\n    return 1\n")
            (root / "tests/test_example.py").write_text(
                "from app.example import value\n", encoding="utf-8"
            )
            long_running = _LongRunning()
            service = ProjectIntelligenceService(
                root, long_running_service=long_running
            )
            selected = service.store.save_opportunity({
                "opportunity_id": "op-safe",
                "title": "Bezpieczna poprawka",
                "objective": "Przygotuj małą poprawkę i zatrzymaj się na podglądzie.",
                "target": "app/example.py",
                "source": "test",
                "severity": "MEDIUM",
                "issue_type": "QUALITY",
                "fingerprint": "safe-preview-fingerprint",
                "value_score": 70,
                "risk_score": 20,
                "effort_score": 10,
                "confidence": 0.9,
                "final_score": 60,
                "status": "READY",
            })
            result = service._dispatch_selected(selected)
            context = long_running.calls[0][1]
        self.assertTrue(result["success"])
        self.assertFalse(context["auto_approve"])
        self.assertEqual(context["optimization_constraints"]["min_score"], 50.0)
        self.assertEqual(context["optimization_constraints"]["max_campaigns"], 1)


    def test_foundation_policy_is_bounded_and_approval_gated(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = json.loads(
            (root / "config/b191_b200_foundation_2.json").read_text(
                encoding="utf-8"
            )
        )
        safety = dict(policy.get("safety", {}) or {})
        self.assertFalse(safety["gmail_automatic_send"])
        self.assertTrue(safety["gmail_send_requires_confirmation"])
        self.assertFalse(safety["autodev_auto_approve"])
        self.assertEqual(safety["autodev_max_active_jobs"], 1)

    def test_foundation_sources_keep_legacy_bounds_and_safe_markers(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/client_experience_window.py": 440,
            "app/gui/client_command_runtime.py": 180,
            "app/gui/client_theme.py": 120,
            "app/gui/main_window.py": 440,
            "app/natural_actions/advanced_actions.py": 190,
            "app/natural_actions/service.py": 320,
            "app/online_assistant/gmail_live_center.py": 190,
            "app/online_assistant/google_workspace_gmail_live.py": 230,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
        brain = (root / "app/ai/brain.py").read_text(encoding="utf-8")
        self.assertIn('"auto_approve": False', brain)
        self.assertIn("interval_seconds=15.0", brain)
        client = (root / "app/gui/client_experience_window.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ClientExperienceV2", client)
        self.assertIn("_client_async_enabled = True", (
            root / "app/gui/main_window.py"
        ).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

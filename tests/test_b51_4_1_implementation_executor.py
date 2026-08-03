from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.ai.software_engineer import (
    ImplementationExecutionPolicy,
    ImplementationExecutor,
)


class FakeDeveloperAgent:

    def __init__(
        self,
        *,
        success: bool = True,
        content: str = "VALUE = 2\n",
    ) -> None:
        self.success = success
        self.content = content
        self.calls: list[dict[str, object]] = []

    def generate_code_proposal(
        self,
        **kwargs,
    ):
        self.calls.append(kwargs)

        return {
            "success": self.success,
            "proposed_content": (
                self.content
                if self.success
                else ""
            ),
            "strategy": "FAKE_LLM",
            "errors": (
                []
                if self.success
                else ["generation failed"]
            ),
        }


class FakeDeveloperController:

    def __init__(
        self,
        *,
        status: str = "waiting_for_approval",
        success: bool = True,
    ) -> None:
        self.status = status
        self.success = success
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        request,
        *,
        auto_approve: bool,
        auto_rollback: bool,
    ):
        self.calls.append(
            {
                "request": request,
                "auto_approve": auto_approve,
                "auto_rollback": auto_rollback,
            }
        )

        return SimpleNamespace(
            success=self.success,
            status=self.status,
            message="workflow result",
            as_dict=lambda: {
                "success": self.success,
                "status": self.status,
                "message": "workflow result",
                "preview": "preview",
            },
        )


class ImplementationExecutorTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp_dir.name
        )
        target = self.root / "app/sample.py"
        target.parent.mkdir(
            parents=True
        )
        target.write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )
        self.target = target

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def scheduled_task(
        self,
        *,
        category: str = "implementation",
        payload: dict | None = None,
    ) -> dict:
        return {
            "task_id": "task-1",
            "title": "Update sample",
            "category": category,
            "payload": {
                "description": "Update sample value.",
                "category": category,
                "path": str(self.target),
                **dict(payload or {}),
            },
        }

    def test_uses_direct_proposed_content(self) -> None:
        controller = FakeDeveloperController()
        agent = FakeDeveloperAgent()

        result = ImplementationExecutor(
            self.root,
            developer_controller=controller,
            developer_agent=agent,
        ).execute(
            self.scheduled_task(
                payload={
                    "proposed_content": "VALUE = 2\n",
                }
            )
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "PREVIEW_READY",
        )
        self.assertEqual(len(agent.calls), 0)
        self.assertEqual(
            controller.calls[0][
                "request"
            ].proposed_content,
            "VALUE = 2\n",
        )

    def test_generates_content_when_missing(self) -> None:
        controller = FakeDeveloperController()
        agent = FakeDeveloperAgent(
            content="VALUE = 3\n"
        )

        result = ImplementationExecutor(
            self.root,
            developer_controller=controller,
            developer_agent=agent,
        ).execute(
            self.scheduled_task()
        )

        self.assertTrue(
            result["generation"]["used"]
        )
        self.assertEqual(len(agent.calls), 1)
        self.assertEqual(
            controller.calls[0][
                "request"
            ].proposed_content,
            "VALUE = 3\n",
        )

    def test_missing_target_is_rejected(self) -> None:
        result = ImplementationExecutor(
            self.root,
            developer_controller=(
                FakeDeveloperController()
            ),
            developer_agent=FakeDeveloperAgent(),
        ).execute(
            {
                "task_id": "task-1",
                "title": "Task",
                "category": "implementation",
                "payload": {
                    "description": "Task",
                },
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "TARGET_REQUIRED",
        )

    def test_non_code_task_is_rejected(self) -> None:
        result = ImplementationExecutor(
            self.root,
            developer_controller=(
                FakeDeveloperController()
            ),
            developer_agent=FakeDeveloperAgent(),
        ).execute(
            self.scheduled_task(
                category="analysis"
            )
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "NON_CODE_TASK",
        )

    def test_preview_mode_does_not_auto_approve(self) -> None:
        controller = FakeDeveloperController()

        ImplementationExecutor(
            self.root,
            developer_controller=controller,
            developer_agent=FakeDeveloperAgent(),
        ).execute(
            self.scheduled_task(),
            auto_approve=False,
        )

        self.assertFalse(
            controller.calls[0]["auto_approve"]
        )
        self.assertTrue(
            controller.calls[0]["auto_rollback"]
        )

    def test_auto_execution_maps_completed_status(self) -> None:
        controller = FakeDeveloperController(
            status="completed",
            success=True,
        )

        result = ImplementationExecutor(
            self.root,
            developer_controller=controller,
            developer_agent=FakeDeveloperAgent(),
        ).execute(
            self.scheduled_task(),
            auto_approve=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "COMPLETED",
        )
        self.assertTrue(
            controller.calls[0]["auto_approve"]
        )

    def test_generation_failure_stops_execution(self) -> None:
        controller = FakeDeveloperController()
        agent = FakeDeveloperAgent(
            success=False
        )

        result = ImplementationExecutor(
            self.root,
            developer_controller=controller,
            developer_agent=agent,
        ).execute(
            self.scheduled_task()
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "PROPOSAL_FAILED",
        )
        self.assertEqual(len(controller.calls), 0)

    def test_policy_can_disable_generation(self) -> None:
        controller = FakeDeveloperController()

        result = ImplementationExecutor(
            self.root,
            developer_controller=controller,
            developer_agent=FakeDeveloperAgent(),
            policy=ImplementationExecutionPolicy(
                allow_code_generation=False,
            ),
        ).execute(
            self.scheduled_task()
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "PROPOSAL_FAILED",
        )
        self.assertEqual(len(controller.calls), 0)


if __name__ == "__main__":
    unittest.main()

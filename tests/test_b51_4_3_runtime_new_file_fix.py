from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.execution_recovery import (
    ExecutionRecoveryOrchestrator,
    ExecutionRecoveryPolicy,
)
from app.ai.software_engineer.implementation_executor import (
    ImplementationExecutor,
)


class FakeAgent:

    def __init__(
        self,
        *,
        content: str = (
            "class DemoFeature:\n"
            "    pass\n"
        ),
        success: bool = True,
    ) -> None:
        self.content = content
        self.success = success
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
                else ["Model nie wygenerował kodu."]
            ),
        }


class FakeController:

    def __init__(
        self,
        *,
        success: bool = True,
        status: str = "completed",
    ) -> None:
        self.success = success
        self.status = status
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
            as_dict=lambda: {
                "success": self.success,
                "status": self.status,
                "errors": (
                    []
                    if self.success
                    else ["Walidacja nie przeszła."]
                ),
                "data": {
                    "rollback_attempted": (
                        not self.success
                    ),
                    "rollback_success": (
                        not self.success
                    ),
                },
            }
        )


class RuntimeNewFileTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp_dir.name
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def task(
        self,
        target: Path,
    ) -> dict:
        return {
            "task_id": "demo-task",
            "title": "Create DemoFeature",
            "category": "implementation",
            "payload": {
                "description": (
                    "Utwórz klasę DemoFeature."
                ),
                "category": "implementation",
                "path": str(target),
            },
        }

    def test_missing_python_file_can_be_prepared(self) -> None:
        target = (
            self.root
            / "app/demo_feature.py"
        )
        agent = FakeAgent()
        controller = FakeController()

        result = ImplementationExecutor(
            self.root,
            developer_agent=agent,
            developer_controller=controller,
        ).execute(
            self.task(target),
            auto_approve=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "COMPLETED",
        )
        self.assertTrue(
            result["created_new_file"]
        )
        self.assertTrue(target.exists())
        self.assertEqual(len(agent.calls), 1)
        self.assertEqual(
            controller.calls[0][
                "request"
            ].proposed_content,
            (
                "class DemoFeature:\n"
                "    pass\n"
            ),
        )

    def test_generation_failure_removes_placeholder(self) -> None:
        target = (
            self.root
            / "app/demo_feature.py"
        )

        result = ImplementationExecutor(
            self.root,
            developer_agent=FakeAgent(
                success=False
            ),
            developer_controller=FakeController(),
        ).execute(
            self.task(target),
            auto_approve=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "PROPOSAL_FAILED",
        )
        self.assertFalse(target.exists())

    def test_failed_workflow_removes_placeholder(self) -> None:
        target = (
            self.root
            / "app/demo_feature.py"
        )

        result = ImplementationExecutor(
            self.root,
            developer_agent=FakeAgent(),
            developer_controller=FakeController(
                success=False,
                status="failed_and_rolled_back",
            ),
        ).execute(
            self.task(target),
            auto_approve=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "FAILED_AND_ROLLED_BACK",
        )
        self.assertFalse(target.exists())

    def test_target_outside_project_is_rejected(self) -> None:
        outside = (
            self.root.parent
            / f"{self.root.name}_outside.py"
        )

        outside.unlink(
            missing_ok=True,
        )
        self.addCleanup(
            outside.unlink,
            missing_ok=True,
        )

        result = ImplementationExecutor(
            self.root,
            developer_agent=FakeAgent(),
            developer_controller=FakeController(),
        ).execute(
            self.task(outside),
            auto_approve=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "TARGET_INVALID",
        )
        self.assertFalse(outside.exists())


class FakeRecoveryExecutor:

    def __init__(self) -> None:
        self.calls = 0

    def execute(
        self,
        task,
        *,
        auto_approve: bool,
        auto_rollback: bool,
    ):
        self.calls += 1

        if self.calls == 1:
            return {
                "success": False,
                "status": "PROPOSAL_FAILED",
                "errors": [
                    "Pusta odpowiedź modelu."
                ],
            }

        return {
            "success": True,
            "status": "COMPLETED",
            "workflow": {
                "success": True,
                "status": "completed",
            },
        }


class RuntimeRecoveryTests(unittest.TestCase):

    def test_generation_failure_is_retried(self) -> None:
        executor = FakeRecoveryExecutor()

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
            policy=ExecutionRecoveryPolicy(
                max_attempts=2,
            ),
        ).execute_with_recovery(
            {
                "task_id": "task",
                "title": "Task",
                "payload": {},
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["attempt_count"],
            2,
        )
        self.assertEqual(executor.calls, 2)

    def test_controller_surfaces_nested_errors(self) -> None:
        errors = (
            AutonomousSoftwareEngineerController
            ._execution_errors(
                {
                    "errors": [
                        "Błąd główny"
                    ],
                    "final_result": {
                        "errors": [
                            "Błąd generowania"
                        ],
                    },
                    "attempts": [
                        {
                            "errors": [
                                "Błąd próby"
                            ],
                        }
                    ],
                }
            )
        )

        self.assertEqual(
            errors,
            [
                "Błąd główny",
                "Błąd generowania",
                "Błąd próby",
            ],
        )


if __name__ == "__main__":
    unittest.main()

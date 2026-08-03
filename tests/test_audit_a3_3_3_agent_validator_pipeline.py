from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_pipeline import AutoDevPipeline
from app.autodev.autodev_pipeline_task_service import (
    AutoDevPipelineTaskService,
)
from app.autodev.autonomous_task_queue import TaskPriority
from app.autodev.developer_agent import DeveloperAgent
from app.autodev.developer_agent_proposal_service import (
    DeveloperAgentProposalService,
)
from app.autodev.developer_validation_service import (
    DeveloperValidationService,
)
from app.autodev.developer_validator import DeveloperValidator


class AuditA333AgentValidatorPipelineTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_large_files_are_reduced(self) -> None:
        limits = {
            "app/autodev/developer_agent.py": 950,
            "app/autodev/developer_validator.py": 220,
            "app/autodev/autodev_pipeline.py": 530,
        }
        failures: list[str] = []

        for relative, maximum in limits.items():
            count = len(
                (self.project_root / relative)
                .read_text(encoding="utf-8")
                .splitlines()
            )
            if count >= maximum:
                failures.append(
                    f"{relative}: {count} >= {maximum}"
                )

        self.assertEqual(failures, [], "\n".join(failures))

    def test_services_are_stateless(self) -> None:
        services = (
            DeveloperAgentProposalService(),
            DeveloperValidationService(),
            AutoDevPipelineTaskService(),
        )
        self.assertTrue(all(vars(service) == {} for service in services))

    def test_moved_methods_are_thin_wrappers(self) -> None:
        expectations = {
            "app/autodev/developer_agent.py": (
                "DeveloperAgent",
                (
                    "prepare_planned_task",
                    "generate_code_proposal",
                    "review_code_proposal",
                    "_retry_after_review",
                    "_proposal_for_task",
                ),
            ),
            "app/autodev/developer_validator.py": (
                "DeveloperValidator",
                (
                    "validate_file",
                    "validate_files",
                    "check_syntax",
                    "compile_file",
                    "run_import_test",
                    "run_test_suite",
                    "analyze_failure",
                    "_matching_test_modules",
                ),
            ),
            "app/autodev/autodev_pipeline.py": (
                "AutoDevPipeline",
                (
                    "submit",
                    "submit_file_change",
                    "submit_function_change",
                    "submit_multi_file_change",
                    "_apply_execution_flags",
                    "wait_for_task",
                    "run_until_idle",
                ),
            ),
        }
        failures: list[str] = []

        for relative, (class_name, names) in expectations.items():
            tree = ast.parse(
                (self.project_root / relative).read_text(encoding="utf-8")
            )
            cls = next(
                node for node in tree.body
                if isinstance(node, ast.ClassDef)
                and node.name == class_name
            )
            methods = {
                node.name: node for node in cls.body
                if isinstance(node, ast.FunctionDef)
            }
            for name in names:
                length = methods[name].end_lineno - methods[name].lineno + 1
                if length > 22:
                    failures.append(f"{relative}:{name}={length}")

        self.assertEqual(failures, [], "\n".join(failures))

    def test_agent_invalid_planned_task_behavior_is_preserved(self) -> None:
        agent = DeveloperAgent.__new__(DeveloperAgent)

        with self.assertRaises(TypeError):
            agent.prepare_planned_task("not-a-dict")

    def test_validator_syntax_behavior_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            valid = root / "valid.py"
            invalid = root / "invalid.py"
            valid.write_text("value = 1\n", encoding="utf-8")
            invalid.write_text("def broken(:\n", encoding="utf-8")

            validator = DeveloperValidator(project_root=root)
            self.assertTrue(validator.check_syntax(str(valid)).success)
            self.assertFalse(validator.check_syntax(str(invalid)).success)

    def test_pipeline_file_submission_behavior_is_preserved(self) -> None:
        pipeline = AutoDevPipeline.__new__(AutoDevPipeline)
        task = object()
        pipeline.queue = MagicMock()
        pipeline.queue.create_task.return_value = task
        pipeline.scheduler = MagicMock()

        result = pipeline.submit_file_change(
            title="Demo",
            goal="Dodaj Demo",
            path="app/demo.py",
            proposed_content="value = 1\n",
            priority=TaskPriority.HIGH,
            auto_approve=True,
            auto_execute=False,
            auto_rollback=True,
        )

        self.assertIs(result, task)
        payload = pipeline.queue.create_task.call_args.kwargs["payload"]
        self.assertEqual(payload["path"], "app/demo.py")
        self.assertEqual(payload["mode"], "file")
        self.assertTrue(payload["auto_approve"])
        self.assertFalse(payload["auto_execute"])
        self.assertTrue(payload["auto_rollback"])
        pipeline.scheduler.wake.assert_called_once()


if __name__ == "__main__":
    unittest.main()

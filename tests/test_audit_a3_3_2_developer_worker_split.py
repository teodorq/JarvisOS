from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_worker import AutoDevWorker
from app.autodev.autodev_worker_request_service import (
    AutoDevWorkerRequestService,
)
from app.autodev.developer_controller import (
    DeveloperController,
)
from app.autodev.developer_controller_workflow_service import (
    DeveloperControllerWorkflowService,
)


class AuditA332DeveloperWorkerSplitTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(
            __file__
        ).resolve().parents[1]

    def test_large_files_are_reduced(self) -> None:
        limits = {
            "app/autodev/developer_controller.py": 800,
            "app/autodev/autodev_worker.py": 800,
        }
        failures: list[str] = []

        for relative, maximum in limits.items():
            lines = len(
                (
                    self.project_root
                    / relative
                ).read_text(
                    encoding="utf-8",
                ).splitlines()
            )

            if lines >= maximum:
                failures.append(
                    f"{relative}: {lines} >= {maximum}"
                )

        self.assertEqual(
            failures,
            [],
            "\n".join(failures),
        )

    def test_controller_workflow_methods_are_wrappers(self) -> None:
        source = (
            self.project_root
            / "app/autodev/developer_controller.py"
        ).read_text(
            encoding="utf-8",
        )
        tree = ast.parse(source)
        target_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DeveloperController"
        )
        methods = {
            node.name: node
            for node in target_class.body
            if isinstance(node, ast.FunctionDef)
        }

        for name in (
            "enqueue_director_plan",
            "prepare",
            "execute",
        ):
            self.assertLessEqual(
                methods[name].end_lineno
                - methods[name].lineno
                + 1,
                14,
            )

    def test_worker_request_methods_are_wrappers(self) -> None:
        source = (
            self.project_root
            / "app/autodev/autodev_worker.py"
        ).read_text(
            encoding="utf-8",
        )
        tree = ast.parse(source)
        target_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "AutoDevWorker"
        )
        methods = {
            node.name: node
            for node in target_class.body
            if isinstance(node, ast.FunctionDef)
        }

        for name in (
            "_build_request",
            "_resolve_code_inputs",
            "_find_code_proposal",
        ):
            self.assertLessEqual(
                methods[name].end_lineno
                - methods[name].lineno
                + 1,
                18,
            )

    def test_services_are_stateless(self) -> None:
        self.assertEqual(
            vars(
                DeveloperControllerWorkflowService()
            ),
            {},
        )
        self.assertEqual(
            vars(
                AutoDevWorkerRequestService()
            ),
            {},
        )

    def test_nested_code_proposal_behavior_is_preserved(self) -> None:
        result = AutoDevWorker._find_code_proposal(
            {
                "context": {
                    "data": {
                        "proposal": {
                            "path": "app/demo.py",
                            "proposed_content": "value = 1\n",
                        }
                    }
                }
            }
        )

        self.assertEqual(
            result["path"],
            "app/demo.py",
        )
        self.assertEqual(
            result["proposed_content"],
            "value = 1\n",
        )

    def test_worker_direct_payload_behavior_is_preserved(self) -> None:
        worker = AutoDevWorker.__new__(
            AutoDevWorker
        )
        worker.developer_agent = MagicMock()

        task = SimpleNamespace(
            task_id="task-1",
            title="Demo",
            description="Dodaj Demo",
            source="test",
            priority=1,
        )
        payload = {
            "path": "app/demo.py",
            "proposed_content": "value = 1\n",
        }

        result = worker._resolve_code_inputs(
            task=task,
            payload=payload,
            goal="Dodaj Demo",
            target="app/demo.py",
            mode="file",
        )

        self.assertEqual(
            result["path"],
            "app/demo.py",
        )
        self.assertEqual(
            result["proposed_content"],
            "value = 1\n",
        )
        worker.developer_agent.generate_code_proposal.assert_not_called()

    def test_empty_director_plan_behavior_is_preserved(self) -> None:
        controller = DeveloperController.__new__(
            DeveloperController
        )
        controller.task_queue = MagicMock()

        result = controller.enqueue_director_plan(
            "",
            {},
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "EMPTY_OBJECTIVE",
        )


if __name__ == "__main__":
    unittest.main()

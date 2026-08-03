"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from app.ai.brain_response_formatter import (
    BrainResponseFormatter,
)
from app.ai.software_engineer import (
    AutonomousSoftwareEngineerController,
    CrossModuleChangePlanner,
    CrossModuleChangeWorkflow,
    MultiFileRefactorExecutor,
    MultiFileRefactorVerifier,
    MultiFileRefactorWorkflow,
)
from app.autodev.execution_result import (
    ExecutionResult,
)


class ForcedCrossModuleFailureVerifier:

    def verify(self, plan, execution):
        status = str(
            execution.get("status", "UNKNOWN")
        ).upper()

        if "ROLLED_BACK" in status:
            return {
                "success": True,
                "status": "VERIFIED",
                "execution_status": status,
                "checked_files": [],
                "unexpected_changes": [],
                "errors": [],
            }

        return {
            "success": False,
            "status": "VERIFICATION_FAILED",
            "execution_status": status,
            "checked_files": [],
            "unexpected_changes": [],
            "errors": [
                "symulowany błąd integracji między modułami",
            ],
        }


class FakeCrossModuleWorkflow:

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, objective, **kwargs):
        self.calls.append(
            {
                "objective": objective,
                **kwargs,
            }
        )
        return {
            "success": True,
            "status": "CROSS_MODULE_PREVIEW_READY",
            "run_id": "cross-run-test",
            "cross_module_plan": {
                "subsystems": {
                    "app.ai": ["app/ai/service.py"],
                    "app.autodev": [
                        "app/autodev/worker.py"
                    ],
                },
                "module_order": [
                    "app.autodev.worker",
                    "app.ai.service",
                ],
                "risk_level": "MEDIUM",
                "refactor_plan": {
                    "files": [
                        {
                            "relative_path": (
                                "app/ai/service.py"
                            ),
                        },
                        {
                            "relative_path": (
                                "app/autodev/worker.py"
                            ),
                        },
                    ],
                },
            },
            "feature_blueprint": {},
            "verification": {
                "status": "VERIFIED",
            },
            "errors": [],
        }


class B5155CrossModuleChangeTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp_dir.name
        ).resolve()
        (self.root / "app/ai").mkdir(
            parents=True
        )
        (self.root / "app/autodev").mkdir(
            parents=True
        )
        (self.root / "tests").mkdir()
        (self.root / "app/__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        (self.root / "app/ai/__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        (
            self.root
            / "app/autodev/__init__.py"
        ).write_text(
            "",
            encoding="utf-8",
        )
        (self.root / "tests/__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        (
            self.root
            / "app/autodev/worker.py"
        ).write_text(
            (
                "def process(value: int) -> int:\n"
                "    return value * 2\n"
            ),
            encoding="utf-8",
        )
        (
            self.root
            / "app/ai/service.py"
        ).write_text(
            (
                "from app.autodev.worker import process\n\n"
                "def calculate(value: int) -> int:\n"
                "    return process(value)\n"
            ),
            encoding="utf-8",
        )
        (
            self.root
            / "app/ai/consumer.py"
        ).write_text(
            (
                "from app.ai.service import calculate\n\n"
                "RESULT = calculate(2)\n"
            ),
            encoding="utf-8",
        )
        (
            self.root
            / "tests/test_integration.py"
        ).write_text(
            (
                "from app.ai.service import calculate\n\n"
                "def test_calculate():\n"
                "    assert calculate(2) >= 1\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def replacements(self) -> dict[str, str]:
        return {
            "app/autodev/worker.py": (
                "def process(value: int) -> int:\n"
                "    result = value * 2\n"
                "    return max(0, result)\n"
            ),
            "app/ai/service.py": (
                "from app.autodev.worker import process\n\n"
                "def calculate(value: int) -> int:\n"
                "    result = process(value)\n"
                "    return max(0, result)\n"
            ),
        }

    def workflow(
        self,
        *,
        verifier=None,
    ) -> CrossModuleChangeWorkflow:
        executor = MultiFileRefactorExecutor(
            self.root
        )
        validator = (
            executor.developer_controller
            .executor
            .validator
        )
        validator.validate_files = lambda files: (
            ExecutionResult(
                success=True,
                step_name="validate_files",
                message="OK",
            )
        )
        validator.run_import_test = lambda: (
            ExecutionResult(
                success=True,
                step_name="import",
                message="OK",
            )
        )
        validator.run_test_suite = lambda **kwargs: (
            ExecutionResult(
                success=True,
                step_name="tests",
                message="OK",
            )
        )
        refactor = MultiFileRefactorWorkflow(
            self.root,
            executor=executor,
            verifier=(
                verifier
                or MultiFileRefactorVerifier(
                    self.root
                )
            ),
        )
        return CrossModuleChangeWorkflow(
            self.root,
            refactor_workflow=refactor,
        )

    def test_planner_detects_subsystems_edges_and_order(
        self,
    ) -> None:
        plan = CrossModuleChangePlanner(
            self.root
        ).plan(
            "Usprawnij przepływ między modułami",
            self.replacements(),
        )

        self.assertFalse(
            plan.blocked,
            plan.blockers,
        )
        self.assertEqual(
            set(plan.subsystems),
            {
                "app.ai",
                "app.autodev",
            },
        )
        self.assertTrue(
            plan.dependency_edges
        )
        self.assertLess(
            plan.module_order.index(
                "app.autodev.worker"
            ),
            plan.module_order.index(
                "app.ai.service"
            ),
        )

    def test_same_subsystem_is_blocked_by_default(
        self,
    ) -> None:
        (
            self.root
            / "app/ai/helper.py"
        ).write_text(
            (
                "def helper(value: int) -> int:\n"
                "    return value\n"
            ),
            encoding="utf-8",
        )
        plan = CrossModuleChangePlanner(
            self.root
        ).plan(
            "Zmień tylko AI",
            {
                "app/ai/service.py": (
                    "from app.autodev.worker import process\n\n"
                    "def calculate(value: int) -> int:\n"
                    "    return process(value) + 1\n"
                ),
                "app/ai/helper.py": (
                    "def helper(value: int) -> int:\n"
                    "    return value + 1\n"
                ),
            },
        )

        self.assertTrue(plan.blocked)
        self.assertIn(
            "dwóch podsystemów",
            " ".join(plan.blockers),
        )

    def test_required_subsystem_is_enforced(
        self,
    ) -> None:
        plan = CrossModuleChangePlanner(
            self.root
        ).plan(
            "Zmień AI i AutoDev",
            self.replacements(),
            required_subsystems=[
                "app.ai",
                "app.autodev",
                "app.gui",
            ],
        )

        self.assertTrue(plan.blocked)
        self.assertIn(
            "app.gui",
            " ".join(plan.blockers),
        )

    def test_plan_reports_impact_and_validation_batches(
        self,
    ) -> None:
        plan = CrossModuleChangePlanner(
            self.root
        ).plan(
            "Usprawnij integrację",
            self.replacements(),
        )

        self.assertIn(
            "app/ai/consumer.py",
            plan.impacted_files,
        )
        self.assertIn(
            "tests/test_integration.py",
            plan.impacted_files,
        )
        self.assertTrue(
            any(
                "tests/test_integration.py" in batch
                for batch in plan.validation_batches
            )
        )
        self.assertGreater(
            plan.estimated_risk,
            plan.refactor_plan.estimated_risk,
        )

    def test_new_cross_module_cycle_is_blocked(
        self,
    ) -> None:
        replacements = self.replacements()
        replacements[
            "app/autodev/worker.py"
        ] = (
            "from app.ai.service import calculate\n\n"
            "def process(value: int) -> int:\n"
            "    return calculate(value)\n"
        )
        plan = CrossModuleChangePlanner(
            self.root
        ).plan(
            "Dodaj błędny cykl",
            replacements,
        )

        self.assertTrue(plan.blocked)
        self.assertTrue(
            plan.refactor_plan.new_import_cycles
        )

    def test_plan_only_preserves_all_files(
        self,
    ) -> None:
        before = {
            path: (
                self.root / path
            ).read_text(
                encoding="utf-8"
            )
            for path in self.replacements()
        }
        result = self.workflow().run(
            "Zmień moduły autonomicznie",
            replacements=self.replacements(),
            auto_execute=False,
        )

        self.assertTrue(
            result["success"],
            result["errors"],
        )
        self.assertEqual(
            result["status"],
            "CROSS_MODULE_PLAN_READY",
        )

        for path, content in before.items():
            self.assertEqual(
                (
                    self.root / path
                ).read_text(
                    encoding="utf-8"
                ),
                content,
            )

    def test_preview_preserves_all_files(
        self,
    ) -> None:
        before = {
            path: (
                self.root / path
            ).read_text(
                encoding="utf-8"
            )
            for path in self.replacements()
        }
        result = self.workflow().run(
            "Zmień moduły autonomicznie",
            replacements=self.replacements(),
            auto_execute=True,
            auto_approve=False,
        )

        self.assertTrue(
            result["success"],
            result["errors"],
        )
        self.assertEqual(
            result["status"],
            "CROSS_MODULE_PREVIEW_READY",
        )

        for path, content in before.items():
            self.assertEqual(
                (
                    self.root / path
                ).read_text(
                    encoding="utf-8"
                ),
                content,
            )

    def test_execution_uses_one_atomic_transaction(
        self,
    ) -> None:
        workflow = self.workflow()
        result = workflow.run(
            "Zmień moduły autonomicznie",
            replacements=self.replacements(),
            auto_execute=True,
            auto_approve=True,
        )

        self.assertTrue(
            result["success"],
            result["errors"],
        )
        self.assertEqual(
            result["status"],
            "CROSS_MODULE_COMPLETED",
        )
        transaction = (
            workflow.refactor_workflow
            .executor
            .developer_controller
            .executor
            .last_transaction
        )
        self.assertEqual(
            len(transaction.changes),
            2,
        )
        self.assertEqual(
            result["cross_module_plan"][
                "subsystem_count"
            ],
            2,
        )

    def test_post_verify_failure_rolls_back_every_module(
        self,
    ) -> None:
        before = {
            path: (
                self.root / path
            ).read_text(
                encoding="utf-8"
            )
            for path in self.replacements()
        }
        result = self.workflow(
            verifier=(
                ForcedCrossModuleFailureVerifier()
            )
        ).run(
            "Zmień moduły autonomicznie",
            replacements=self.replacements(),
            auto_execute=True,
            auto_approve=True,
            auto_rollback=True,
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            (
                "CROSS_MODULE_POST_VERIFY_"
                "FAILED_AND_ROLLED_BACK"
            ),
        )
        self.assertTrue(
            result["rollback"]["success"]
        )

        for path, content in before.items():
            self.assertEqual(
                (
                    self.root / path
                ).read_text(
                    encoding="utf-8"
                ),
                content,
            )

    def test_controller_routes_cross_module_workflow(
        self,
    ) -> None:
        fake = FakeCrossModuleWorkflow()
        controller = AutonomousSoftwareEngineerController(
            project_root=self.root,
            cross_module_workflow=fake,
        )
        result = controller.handle(
            "Wykonaj zmianę między modułami",
            {
                "operation": "cross_module_change",
                "replacements": self.replacements(),
                "auto_execute": False,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["run_id"],
            "cross-run-test",
        )
        self.assertEqual(
            len(fake.calls),
            1,
        )
        self.assertEqual(
            fake.calls[0]["replacements"],
            self.replacements(),
        )

    def test_controller_routes_target_list_for_proposals(
        self,
    ) -> None:
        fake = FakeCrossModuleWorkflow()
        controller = AutonomousSoftwareEngineerController(
            project_root=self.root,
            cross_module_workflow=fake,
        )
        result = controller.handle(
            (
                "Cross module change "
                "app/ai/service.py "
                "app/autodev/worker.py"
            ),
            {
                "cross_module": True,
                "targets": [
                    "app/ai/service.py",
                    "app/autodev/worker.py",
                ],
                "auto_execute": False,
            },
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            fake.calls[0]["targets"],
            [
                "app/ai/service.py",
                "app/autodev/worker.py",
            ],
        )
        self.assertIsNone(
            fake.calls[0]["replacements"]
        )

    def test_formatter_exports_and_size_limits(
        self,
    ) -> None:
        response = FakeCrossModuleWorkflow().run(
            "Zmiana modułów"
        )
        formatted = (
            BrainResponseFormatter()
            ._format_software_engineer_response(
                response
            )
        )

        self.assertIn(
            "Zmiana między modułami",
            formatted,
        )
        self.assertIn(
            "app.ai",
            formatted,
        )

        from app.ai import software_engineer as package

        self.assertTrue(
            hasattr(
                package,
                "CrossModuleChangeWorkflow",
            )
        )
        project_root = Path(
            __file__
        ).resolve().parents[1]
        controller_source = (
            project_root
            / "app/ai/software_engineer/"
            "autonomous_software_engineer.py"
        ).read_text(
            encoding="utf-8"
        )
        router_source = (
            project_root
            / "app/ai/software_engineer/"
            "software_engineer_command_router.py"
        ).read_text(
            encoding="utf-8"
        )
        self.assertLess(
            len(controller_source.splitlines()),
            440,
        )
        self.assertLess(
            len(router_source.splitlines()),
            500,
        )
        ast.parse(controller_source)
        ast.parse(router_source)


if __name__ == "__main__":
    unittest.main()

"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from app.ai.software_engineer import (
    AutonomousSoftwareEngineerController,
    MultiFileRefactorAnalyzer,
    MultiFileRefactorExecutor,
    MultiFileRefactorProposalGenerator,
    MultiFileRefactorVerifier,
    MultiFileRefactorWorkflow,
)
from app.autodev.execution_result import (
    ExecutionResult,
)


class ForcedRefactorFailureVerifier:

    def verify(
        self,
        plan,
        execution,
    ):
        status = str(
            execution.get(
                "status",
                "UNKNOWN",
            )
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
                "symulowany błąd końcowej weryfikacji",
            ],
        }




class FakeDeveloperAgent:

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_code_proposal(
        self,
        *,
        target,
        goal,
        task,
    ):
        self.calls.append(
            {
                "target": target,
                "goal": goal,
                "task": task,
            }
        )
        function_name = (
            "public_api"
            if str(target).endswith(
                "alpha.py"
            )
            else "beta_value"
        )
        operator = (
            "+"
            if function_name == "public_api"
            else "*"
        )
        return {
            "success": True,
            "target": target,
            "proposed_content": (
                f"def {function_name}(value: int) -> int:\n"
                f"    result = value {operator} 2\n"
                "    return result\n"
            ),
            "strategy": "fake_reviewed_refactor",
            "errors": [],
            "metadata": {
                "ai_review": {
                    "approved": True,
                },
            },
        }


class FakeRefactorWorkflow:

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(
        self,
        objective,
        **kwargs,
    ):
        self.calls.append(
            {
                "objective": objective,
                **kwargs,
            }
        )
        return {
            "run_id": "refactor-run-test",
            "success": True,
            "status": "REFACTOR_PREVIEW_READY",
            "objective": objective,
            "refactor_plan": {
                "files": [],
                "impacted_files": [],
            },
            "feature_blueprint": {
                "feature_name": "MultiFileRefactor",
                "package_path": (
                    "existing_project_files"
                ),
                "files": [],
                "metadata": {
                    "operation": "refactor",
                },
            },
            "execution": {
                "files_count": 0,
            },
            "verification": {
                "success": True,
                "status": "VERIFIED",
            },
            "errors": [],
        }


class B5154MultiFileRefactorTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )
        self.root = Path(
            self.temp_dir.name
        ).resolve()
        package = self.root / "app/pkg"
        package.mkdir(
            parents=True
        )
        (self.root / "app/__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        (package / "__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        (package / "alpha.py").write_text(
            (
                "def public_api(value: int) -> int:\n"
                "    return value + 1\n"
            ),
            encoding="utf-8",
        )
        (package / "beta.py").write_text(
            (
                "def beta_value(value: int) -> int:\n"
                "    return value * 2\n"
            ),
            encoding="utf-8",
        )
        (package / "consumer.py").write_text(
            (
                "from app.pkg.alpha import public_api\n\n"
                "RESULT = public_api(2)\n"
            ),
            encoding="utf-8",
        )
        tests_root = self.root / "tests"
        tests_root.mkdir()
        (tests_root / "__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        (tests_root / "test_pkg.py").write_text(
            (
                "from app.pkg.alpha import public_api\n\n"
                "def test_value():\n"
                "    assert public_api(1) >= 1\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def replacements(
        self,
    ) -> dict[str, str]:
        return {
            "app/pkg/alpha.py": (
                "def public_api(value: int) -> int:\n"
                "    result = value + 1\n"
                "    return max(0, result)\n"
            ),
            "app/pkg/beta.py": (
                "def beta_value(value: int) -> int:\n"
                "    result = value * 2\n"
                "    return max(0, result)\n"
            ),
        }

    def real_workflow(
        self,
        *,
        verifier=None,
    ) -> MultiFileRefactorWorkflow:
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

        return MultiFileRefactorWorkflow(
            self.root,
            executor=executor,
            verifier=(
                verifier
                or MultiFileRefactorVerifier(
                    self.root
                )
            ),
        )

    def test_analyzer_reports_dependents_references_and_risk(
        self,
    ) -> None:
        plan = MultiFileRefactorAnalyzer(
            self.root
        ).analyze(
            "Usprawnij obliczenia pakietu",
            self.replacements(),
        )
        alpha = plan.file_map()[
            "app/pkg/alpha.py"
        ]

        self.assertFalse(
            plan.blocked,
            plan.blockers,
        )
        self.assertIn(
            "app/pkg/consumer.py",
            plan.impacted_files,
        )
        self.assertIn(
            "tests/test_pkg.py",
            plan.impacted_files,
        )
        self.assertIn(
            "public_api",
            alpha.changed_symbols,
        )
        self.assertGreater(
            plan.estimated_risk,
            0,
        )
        self.assertEqual(
            set(plan.rollback_scope),
            {
                "app/pkg/alpha.py",
                "app/pkg/beta.py",
            },
        )

    def test_public_symbol_removal_with_references_is_blocked(
        self,
    ) -> None:
        replacements = self.replacements()
        replacements[
            "app/pkg/alpha.py"
        ] = (
            "def internal_value(value: int) -> int:\n"
            "    return value + 1\n"
        )
        plan = MultiFileRefactorAnalyzer(
            self.root
        ).analyze(
            "Usuń stare API",
            replacements,
        )

        self.assertTrue(
            plan.blocked
        )
        self.assertIn(
            "public_api",
            " ".join(
                plan.blockers
            ),
        )

    def test_public_symbol_removal_requires_explicit_override(
        self,
    ) -> None:
        replacements = self.replacements()
        replacements[
            "app/pkg/alpha.py"
        ] = (
            "def internal_value(value: int) -> int:\n"
            "    return value + 1\n"
        )
        plan = MultiFileRefactorAnalyzer(
            self.root
        ).analyze(
            "Usuń stare API świadomie",
            replacements,
            allow_public_symbol_removal=True,
        )

        self.assertFalse(
            any(
                "public_api" in item
                for item in plan.blockers
            )
        )
        self.assertIn(
            "public_api",
            plan.file_map()[
                "app/pkg/alpha.py"
            ].removed_public_symbols,
        )

    def test_new_import_cycle_is_blocked(
        self,
    ) -> None:
        plan = MultiFileRefactorAnalyzer(
            self.root
        ).analyze(
            "Dodaj błędne zależności cykliczne",
            {
                "app/pkg/alpha.py": (
                    "from app.pkg.beta import beta_value\n\n"
                    "def public_api(value: int) -> int:\n"
                    "    return beta_value(value)\n"
                ),
                "app/pkg/beta.py": (
                    "from app.pkg.alpha import public_api\n\n"
                    "def beta_value(value: int) -> int:\n"
                    "    return public_api(value)\n"
                ),
            },
        )

        self.assertTrue(
            plan.blocked
        )
        self.assertTrue(
            plan.new_import_cycles
        )
        self.assertIn(
            "cykle importów",
            " ".join(
                plan.blockers
            ),
        )

    def test_preview_preserves_every_file(
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
        result = self.real_workflow().run(
            "Usprawnij dwa moduły",
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
            "REFACTOR_PREVIEW_READY",
        )
        self.assertEqual(
            result["verification"]["status"],
            "VERIFIED",
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

    def test_execution_updates_all_files_in_one_transaction(
        self,
    ) -> None:
        workflow = self.real_workflow()
        result = workflow.run(
            "Usprawnij dwa moduły",
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
            "REFACTOR_COMPLETED",
        )
        self.assertEqual(
            result["verification"]["status"],
            "VERIFIED",
        )
        transaction = (
            workflow.executor
            .developer_controller
            .executor
            .last_transaction
        )
        self.assertEqual(
            len(transaction.changes),
            2,
        )
        self.assertTrue(
            all(
                item.operation == "update"
                for item in transaction.changes
            )
        )
        self.assertIsNotNone(
            workflow.get_run(
                result["run_id"]
            )
        )
        self.assertTrue(
            str(
                result["report_path"]
            ).endswith(
                "multi_file_refactor_runs.json"
            )
        )

    def test_post_verification_failure_restores_all_files(
        self,
    ) -> None:
        alpha_before = (
            self.root
            / "app/pkg/alpha.py"
        ).read_text(
            encoding="utf-8"
        )
        beta_before = (
            self.root
            / "app/pkg/beta.py"
        ).read_text(
            encoding="utf-8"
        )
        workflow = self.real_workflow(
            verifier=(
                ForcedRefactorFailureVerifier()
            )
        )
        result = workflow.run(
            "Usprawnij dwa moduły",
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
                "REFACTOR_POST_VERIFY_FAILED_"
                "AND_ROLLED_BACK"
            ),
        )
        self.assertTrue(
            result["rollback"]["success"]
        )
        self.assertEqual(
            (
                self.root
                / "app/pkg/alpha.py"
            ).read_text(
                encoding="utf-8"
            ),
            alpha_before,
        )
        self.assertEqual(
            (
                self.root
                / "app/pkg/beta.py"
            ).read_text(
                encoding="utf-8"
            ),
            beta_before,
        )

    def test_verifier_detects_collateral_file_change(
        self,
    ) -> None:
        analyzer = MultiFileRefactorAnalyzer(
            self.root
        )
        plan = analyzer.analyze(
            "Usprawnij dwa moduły",
            self.replacements(),
        )

        for path, content in self.replacements().items():
            (
                self.root / path
            ).write_text(
                content,
                encoding="utf-8",
            )

        (
            self.root
            / "app/pkg/consumer.py"
        ).write_text(
            "RESULT = 999\n",
            encoding="utf-8",
        )
        verification = MultiFileRefactorVerifier(
            self.root
        ).verify(
            plan,
            {
                "status": "COMPLETED",
                "files": list(
                    self.replacements()
                ),
            },
        )

        self.assertFalse(
            verification["success"]
        )
        self.assertIn(
            "app/pkg/consumer.py",
            verification[
                "unexpected_changes"
            ],
        )

    def test_controller_routes_existing_refactor_workflow(
        self,
    ) -> None:
        fake = FakeRefactorWorkflow()
        controller = (
            AutonomousSoftwareEngineerController(
                project_root=self.root,
                multi_file_refactor_workflow=fake,
            )
        )
        result = controller.handle(
            (
                "Zrefaktoryzuj wieloplikowo "
                "pakiet obliczeń"
            ),
            {
                "operation": "refactor",
                "replacements": (
                    self.replacements()
                ),
                "auto_execute": True,
                "auto_approve": False,
            },
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["run_id"],
            "refactor-run-test",
        )
        self.assertEqual(
            len(fake.calls),
            1,
        )
        self.assertEqual(
            fake.calls[0]["replacements"],
            self.replacements(),
        )


    def test_proposal_generator_builds_all_targets_without_writes(
        self,
    ) -> None:
        agent = FakeDeveloperAgent()
        generator = (
            MultiFileRefactorProposalGenerator(
                self.root,
                developer_agent=agent,
            )
        )
        before = {
            path: (
                self.root / path
            ).read_text(
                encoding="utf-8"
            )
            for path in (
                "app/pkg/alpha.py",
                "app/pkg/beta.py",
            )
        }
        result = generator.generate(
            "Usprawnij autonomicznie dwa moduły",
            [
                "app/pkg/alpha.py",
                "app/pkg/beta.py",
            ],
        )

        self.assertTrue(
            result["success"],
            result["errors"],
        )
        self.assertEqual(
            set(
                result["replacements"]
            ),
            set(before),
        )
        self.assertEqual(
            len(agent.calls),
            2,
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

    def test_controller_routes_target_list_for_autonomous_proposals(
        self,
    ) -> None:
        fake = FakeRefactorWorkflow()
        controller = (
            AutonomousSoftwareEngineerController(
                project_root=self.root,
                multi_file_refactor_workflow=fake,
            )
        )
        result = controller.handle(
            (
                "Zrefaktoryzuj wieloplikowo "
                "app/pkg/alpha.py app/pkg/beta.py"
            ),
            {
                "operation": "refactor",
                "targets": [
                    "app/pkg/alpha.py",
                    "app/pkg/beta.py",
                ],
                "auto_execute": False,
            },
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            fake.calls[0]["targets"],
            [
                "app/pkg/alpha.py",
                "app/pkg/beta.py",
            ],
        )
        self.assertIsNone(
            fake.calls[0]["replacements"]
        )

    def test_controller_and_router_remain_bounded(
        self,
    ) -> None:
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
            len(
                controller_source.splitlines()
            ),
            440,
        )
        self.assertLess(
            len(
                router_source.splitlines()
            ),
            500,
        )
        ast.parse(
            controller_source
        )
        ast.parse(
            router_source
        )


if __name__ == "__main__":
    unittest.main()

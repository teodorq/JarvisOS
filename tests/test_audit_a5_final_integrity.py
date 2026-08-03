from __future__ import annotations

import ast
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agent.app_manager import AppManager
from app.autodev.safe_patch_executor import (
    SafePatchExecutionPolicy,
    SafePatchExecutor,
)
from app.autodev.test_plan import TestPlan
from app.autodev.test_runner import TestRunner as AutoDevTestRunner
from app.code.code_test_runner import CodeTestRunner


class AuditA5FinalIntegrityTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(
            __file__
        ).resolve().parents[1]

    def test_all_python_sources_parse(self) -> None:
        errors: list[str] = []

        candidates = [
            *(
                self.project_root
                / "app"
            ).rglob("*.py"),
            *(
                self.project_root
                / "tests"
            ).rglob("*.py"),
            self.project_root / "main.py",
        ]

        for path in candidates:
            try:
                ast.parse(
                    path.read_text(
                        encoding="utf-8",
                    ),
                    filename=str(path),
                )
            except Exception as error:
                errors.append(
                    f"{path}: {error}"
                )

        self.assertEqual(
            errors,
            [],
            "\n".join(errors),
        )

    def test_no_hardcoded_user_or_project_paths(self) -> None:
        offenders: list[str] = []

        for path in (
            self.project_root
            / "app"
        ).rglob("*.py"):
            source = path.read_text(
                encoding="utf-8",
            )
            normalized = source.replace(
                "\\\\",
                "/",
            ).casefold()

            if (
                "c:/users/" in normalized
                or "c:/jarvisai" in normalized
            ):
                offenders.append(
                    str(
                        path.relative_to(
                            self.project_root
                        )
                    )
                )

        self.assertEqual(
            offenders,
            [],
        )

    def test_process_creation_is_centralized(self) -> None:
        allowed = {
            "app/core/safe_process.py",
        }
        offenders: list[str] = []

        for path in (
            self.project_root
            / "app"
        ).rglob("*.py"):
            tree = ast.parse(
                path.read_text(
                    encoding="utf-8",
                )
            )
            relative = str(
                path.relative_to(
                    self.project_root
                )
            ).replace(
                "\\",
                "/",
            )

            for node in ast.walk(
                tree
            ):
                if not isinstance(
                    node,
                    ast.Call,
                ):
                    continue

                name = ast.unparse(
                    node.func
                )

                if name == "os.system":
                    offenders.append(
                        f"{relative}:{node.lineno}:os.system"
                    )

                if (
                    name
                    in {
                        "subprocess.Popen",
                        "subprocess.run",
                        "subprocess.call",
                        "subprocess.check_call",
                        "subprocess.check_output",
                    }
                    and relative not in allowed
                ):
                    offenders.append(
                        f"{relative}:{node.lineno}:{name}"
                    )

                for keyword in node.keywords:
                    if (
                        keyword.arg == "shell"
                        and isinstance(
                            keyword.value,
                            ast.Constant,
                        )
                        and keyword.value.value
                        is True
                    ):
                        offenders.append(
                            f"{relative}:{node.lineno}:shell=True"
                        )

        self.assertEqual(
            offenders,
            [],
            "\n".join(offenders),
        )

    def test_requirements_cover_windows_vision_dependencies(
        self,
    ) -> None:
        requirements = {
            line.strip().casefold()
            for line in (
                self.project_root
                / "requirements.txt"
            ).read_text(
                encoding="utf-8",
            ).splitlines()
            if line.strip()
        }

        self.assertIn(
            "pygetwindow",
            requirements,
        )
        self.assertIn(
            "pywin32",
            requirements,
        )

    def test_unknown_app_never_spawns_process(self) -> None:
        runner = MagicMock()
        manager = AppManager(
            project_root=self.project_root,
            process_runner=runner,
        )

        result = manager.open_app(
            "cmd /c calc"
        )

        self.assertIn(
            "Nie znam aplikacji",
            result,
        )
        runner.spawn.assert_not_called()

    def test_test_runner_rejects_non_python_program(self) -> None:
        runner = MagicMock()
        test_runner = AutoDevTestRunner(
            project_root=self.project_root,
            process_runner=runner,
        )
        plan = TestPlan(
            commands=[
                [
                    "cmd.exe",
                    "/c",
                    "echo unsafe",
                ]
            ],
            timeout_seconds=10,
        )

        result = test_runner.run(
            plan
        )

        self.assertFalse(
            result["success"]
        )
        self.assertEqual(
            result["commands_run"],
            1,
        )
        runner.run.assert_not_called()

    def test_test_selector_and_runner_use_active_python(
        self,
    ) -> None:
        from app.autodev.test_selector import (
            TestSelector,
        )

        plan = TestSelector().build_plan(
            [
                "app/demo_feature.py",
            ]
        )

        expected = str(
            Path(
                sys.executable
            ).resolve(
                strict=False
            )
        )

        self.assertTrue(
            plan.commands
        )
        self.assertTrue(
            all(
                command[0] == expected
                for command in plan.commands
            )
        )

    def test_code_import_test_uses_safe_runner(self) -> None:
        runner = MagicMock()
        runner.run.return_value = SimpleNamespace(
            success=True,
            stdout="IMPORT OK\n",
            stderr="",
        )
        code_runner = CodeTestRunner(
            project_root=self.project_root,
            process_runner=runner,
        )

        result = code_runner.run_import_test()

        self.assertIn(
            "IMPORT TEST OK",
            result,
        )
        command = (
            runner.run.call_args.args[0]
        )
        self.assertEqual(
            command[0],
            code_runner.python_executable,
        )

    def test_safe_patch_executor_uses_safe_runner(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "demo.py"
            target.write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )
            runner = MagicMock()
            runner.run.return_value = SimpleNamespace(
                success=True,
                stdout="",
                stderr="",
            )
            executor = SafePatchExecutor(
                policy=SafePatchExecutionPolicy(
                    project_root=root,
                    dry_run=True,
                    run_unit_tests=False,
                ),
                process_runner=runner,
            )

            result = executor._run_compile(
                target
            )

        self.assertEqual(
            result,
            "PY_COMPILE_OK",
        )
        command = (
            runner.run.call_args.args[0]
        )
        self.assertEqual(
            command[0],
            executor.python_executable,
        )

    def test_cleanup_module_is_project_scoped(self) -> None:
        from app.core.project_cleanup import (
            clean_python_caches,
        )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = (
                root
                / "app/demo/__pycache__"
            )
            cache.mkdir(
                parents=True
            )
            (
                cache
                / "demo.cpython-313.pyc"
            ).write_bytes(
                b"cache"
            )

            result = clean_python_caches(
                root
            )

            self.assertFalse(
                cache.exists()
            )
            self.assertGreaterEqual(
                result[
                    "removed_directories"
                ],
                1,
            )


if __name__ == "__main__":
    unittest.main()

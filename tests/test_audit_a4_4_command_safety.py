from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

from app.automation.command_executor import CommandExecutor
from app.autodev.autodev_pipeline_task_service import (
    AutoDevPipelineTaskService,
)
from app.autodev.developer_validator import DeveloperValidator
from app.core.safe_process import (
    ProcessPolicyError,
    SafeProcessRunner,
)


class AuditA44CommandSafetyTests(unittest.TestCase):

    def test_shell_string_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = SafeProcessRunner(
                project_root=temp,
                allowed_executables=[
                    sys.executable,
                ],
            )

            with self.assertRaises(
                ProcessPolicyError
            ):
                runner.run(
                    f"{sys.executable} -V",
                    cwd=temp,
                    timeout=5,
                )

    def test_unapproved_executable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = SafeProcessRunner(
                project_root=temp,
                allowed_executables=[
                    sys.executable,
                ],
            )

            with self.assertRaises(
                ProcessPolicyError
            ):
                runner.run(
                    [
                        "cmd.exe",
                        "/c",
                        "echo unsafe",
                    ],
                    cwd=temp,
                    timeout=5,
                )

    def test_working_directory_outside_project_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            outside = Path(temp) / "outside"
            project.mkdir()
            outside.mkdir()
            runner = SafeProcessRunner(
                project_root=project,
                allowed_executables=[
                    sys.executable,
                ],
            )

            with self.assertRaises(
                ProcessPolicyError
            ):
                runner.run(
                    [
                        sys.executable,
                        "-c",
                        "print('x')",
                    ],
                    cwd=outside,
                    timeout=5,
                )

    def test_timeout_is_structured_and_process_is_stopped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = SafeProcessRunner(
                project_root=temp,
                allowed_executables=[
                    sys.executable,
                ],
                max_timeout_seconds=5,
            )

            result = runner.run(
                [
                    sys.executable,
                    "-c",
                    "import time; time.sleep(3)",
                ],
                cwd=temp,
                timeout=0.1,
            )

            self.assertTrue(
                result.timed_out
            )
            self.assertFalse(
                result.success
            )

    def test_output_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = SafeProcessRunner(
                project_root=temp,
                allowed_executables=[
                    sys.executable,
                ],
                max_output_chars=256,
            )

            result = runner.run(
                [
                    sys.executable,
                    "-S",
                    "-c",
                    "print('x' * 2000)",
                ],
                cwd=temp,
                timeout=5,
            )

            self.assertTrue(
                result.success
            )
            self.assertTrue(
                result.truncated
            )
            self.assertLessEqual(
                len(result.stdout),
                256,
            )

    def test_sensitive_environment_is_not_inherited(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = SafeProcessRunner(
                project_root=temp,
                allowed_executables=[
                    sys.executable,
                ],
            )
            previous = os.environ.get(
                "JARVIS_TEST_SECRET_TOKEN"
            )
            os.environ[
                "JARVIS_TEST_SECRET_TOKEN"
            ] = "do-not-pass"

            try:
                result = runner.run(
                    [
                        sys.executable,
                        "-S",
                        "-c",
                        (
                            "import os; "
                            "print(os.getenv("
                            "'JARVIS_TEST_SECRET_TOKEN', "
                            "'missing'))"
                        ),
                    ],
                    cwd=temp,
                    timeout=5,
                )
            finally:
                if previous is None:
                    os.environ.pop(
                        "JARVIS_TEST_SECRET_TOKEN",
                        None,
                    )
                else:
                    os.environ[
                        "JARVIS_TEST_SECRET_TOKEN"
                    ] = previous

            self.assertEqual(
                result.stdout.strip(),
                "missing",
            )

    def test_validator_rejects_path_outside_project(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            root.mkdir()
            outside = Path(temp) / "outside.py"
            outside.write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )
            validator = DeveloperValidator(
                project_root=root
            )

            result = validator.validate_file(
                str(outside)
            )

            self.assertFalse(
                result.success
            )
            self.assertIn(
                "outside",
                " ".join(
                    result.errors
                ).lower(),
            )

    def test_validator_uses_fixed_python_command(
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
            runner.run.return_value = MagicMock(
                success=True,
                timed_out=False,
                stdout="",
                stderr="",
                as_dict=MagicMock(
                    return_value={
                        "returncode": 0,
                    }
                ),
            )
            validator = DeveloperValidator(
                project_root=root,
                process_runner=runner,
            )

            result = validator.compile_file(
                str(target)
            )

            self.assertTrue(
                result.success
            )
            command = runner.run.call_args.args[0]
            self.assertEqual(
                command[:3],
                [
                    validator.python_executable,
                    "-m",
                    "py_compile",
                ],
            )

    def test_unknown_application_never_spawns_process(
        self,
    ) -> None:
        runner = MagicMock()
        executor = CommandExecutor(
            process_runner=runner
        )

        result = executor.open_app(
            "cmd /c calc"
        )

        self.assertIn(
            "Nie znam aplikacji",
            result,
        )
        runner.spawn.assert_not_called()

    def test_pipeline_rejects_unsafe_wait_values(
        self,
    ) -> None:
        service = AutoDevPipelineTaskService()

        with self.assertRaises(
            ValueError
        ):
            service._safe_wait_values(
                -1,
                0.25,
            )

        with self.assertRaises(
            ValueError
        ):
            service._safe_wait_values(
                10,
                0,
            )


if __name__ == "__main__":
    unittest.main()

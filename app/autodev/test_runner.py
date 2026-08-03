from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from app.autodev.test_plan import TestPlan
from app.core.project_paths import (
    default_project_root,
)
from app.core.safe_process import (
    ProcessPolicyError,
    SafeProcessRunner,
)


class TestRunner:

    def __init__(
        self,
        project_root: str = default_project_root(),
        *,
        process_runner: SafeProcessRunner | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.python_executable = str(
            Path(
                sys.executable
            ).resolve(
                strict=False
            )
        )
        self.process_runner = (
            process_runner
            or SafeProcessRunner(
                project_root=self.project_root,
                allowed_executables=[
                    self.python_executable,
                ],
                max_timeout_seconds=600,
                max_output_chars=12000,
            )
        )

    def run(
        self,
        plan: TestPlan,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        timeout = self._safe_timeout(
            plan.timeout_seconds
        )

        for command in plan.commands:
            try:
                prepared = self._prepare_command(
                    command
                )
                process = self.process_runner.run(
                    prepared,
                    cwd=self.project_root,
                    timeout=timeout,
                )
                item = {
                    "command": list(
                        process.command
                    ),
                    "returncode": (
                        process.returncode
                        if process.returncode
                        is not None
                        else -1
                    ),
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "success": process.success,
                    "timed_out": (
                        process.timed_out
                    ),
                    "truncated": (
                        process.truncated
                    ),
                }

            except (
                ProcessPolicyError,
                TypeError,
                ValueError,
            ) as error:
                item = {
                    "command": (
                        list(command)
                        if isinstance(
                            command,
                            (list, tuple),
                        )
                        else []
                    ),
                    "returncode": -1,
                    "stdout": "",
                    "stderr": (
                        f"{type(error).__name__}: "
                        f"{error}"
                    ),
                    "success": False,
                    "timed_out": False,
                    "truncated": False,
                }

            results.append(
                item
            )

            if not item["success"]:
                break

        success = (
            bool(results)
            and all(
                item["success"]
                for item in results
            )
        )

        return {
            "success": success,
            "status": (
                "PASSED"
                if success
                else "FAILED"
            ),
            "results": results,
            "commands_run": len(
                results
            ),
        }

    def _prepare_command(
        self,
        command,
    ) -> list[str]:
        if (
            not isinstance(
                command,
                (list, tuple),
            )
            or not command
        ):
            raise ProcessPolicyError(
                "Test command must be a non-empty argument list."
            )

        prepared = [
            str(item)
            for item in command
        ]
        executable = Path(
            prepared[0]
        ).name.casefold()

        if executable in {
            "python",
            "python.exe",
            "py",
            "py.exe",
        }:
            prepared[0] = (
                self.python_executable
            )

        if (
            Path(
                prepared[0]
            ).expanduser().resolve(
                strict=False
            )
            != Path(
                self.python_executable
            ).resolve(
                strict=False
            )
        ):
            raise ProcessPolicyError(
                "Only the active Python interpreter is allowed."
            )

        return prepared

    @staticmethod
    def _safe_timeout(
        value,
    ) -> float:
        try:
            timeout = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ProcessPolicyError(
                "Test timeout must be numeric."
            ) from error

        if (
            timeout <= 0
            or timeout > 600
        ):
            raise ProcessPolicyError(
                "Test timeout must be between 0 and 600 seconds."
            )

        return timeout

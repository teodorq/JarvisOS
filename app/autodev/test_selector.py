from __future__ import annotations

from pathlib import Path
import sys

from app.autodev.test_plan import TestPlan


class TestSelector:

    def build_plan(
        self,
        changed_files: list[str],
    ) -> TestPlan:
        files = [
            str(
                Path(path)
            )
            for path in changed_files
            if str(path).strip()
        ]
        commands: list[list[str]] = []
        python_executable = str(
            Path(
                sys.executable
            ).resolve(
                strict=False
            )
        )

        for path in files:
            if (
                Path(path).suffix.casefold()
                == ".py"
            ):
                commands.append(
                    [
                        python_executable,
                        "-m",
                        "py_compile",
                        path,
                    ]
                )

        commands.append(
            [
                python_executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ]
        )

        return TestPlan(
            changed_files=files,
            commands=commands,
        )

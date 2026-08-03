from __future__ import annotations

from pathlib import Path
import sys

from app.code.syntax_checker import (
    SyntaxChecker,
)
from app.core.project_paths import (
    default_project_root,
)
from app.core.safe_process import (
    SafeProcessRunner,
)


class CodeTestRunner:

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        process_runner: SafeProcessRunner | None = None,
    ) -> None:
        self.syntax = SyntaxChecker()
        self.project_root = Path(
            project_root
            or default_project_root()
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
                max_timeout_seconds=30,
                max_output_chars=8000,
            )
        )

    def check_file(
        self,
        path: str,
    ):
        return self.syntax.check_file(
            path
        )

    def run_main_quick(
        self,
    ) -> str:
        return (
            "GUI TEST SKIPPED\n"
            "main.py jest aplikacją GUI i działa ciągle, "
            "więc nie testuję go timeoutem."
        )

    def run_import_test(
        self,
    ) -> str:
        try:
            result = self.process_runner.run(
                [
                    self.python_executable,
                    "-c",
                    (
                        "from app.gui.main_window "
                        "import MainWindow; "
                        "print('IMPORT OK')"
                    ),
                ],
                cwd=self.project_root,
                timeout=15,
            )

            if result.success:
                return (
                    "IMPORT TEST OK\n"
                    + result.stdout
                )

            return (
                "IMPORT TEST FAILED\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        except Exception as error:
            return (
                "IMPORT TEST ERROR: "
                f"{type(error).__name__}: {error}"
            )

    def run_main(
        self,
    ) -> str:
        import_result = (
            self.run_import_test()
        )

        return (
            "PROJECT TEST\n\n"
            f"{import_result}\n\n"
            f"{self.run_main_quick()}"
        )

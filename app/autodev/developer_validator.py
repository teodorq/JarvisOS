from app.core.project_paths import (
    default_project_root,
)

import sys
from pathlib import Path

from app.autodev.developer_validation_service import (
    DeveloperValidationService,
)
from app.autodev.execution_result import ExecutionResult
from app.core.safe_process import SafeProcessRunner


_DEVELOPER_VALIDATION_SERVICE = DeveloperValidationService()


class DeveloperValidator:

    def __init__(
        self,
        project_root=default_project_root(),
        test_timeout: int = 180,
        process_runner: SafeProcessRunner | None = None,
    ):
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
        self.test_timeout = min(
            600,
            max(
                30,
                int(test_timeout),
            ),
        )
        self.process_runner = (
            process_runner
            or SafeProcessRunner(
                project_root=self.project_root,
                allowed_executables=[
                    self.python_executable,
                ],
                max_timeout_seconds=(
                    self.test_timeout
                ),
                max_output_chars=8000,
            )
        )

    def _resolve_path(self, path: str) -> Path:
        file_path = Path(
            path
        ).expanduser()

        if not file_path.is_absolute():
            file_path = (
                self.project_root
                / file_path
            )

        unresolved = file_path
        file_path = file_path.resolve(
            strict=False
        )

        try:
            file_path.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Validation target is outside the project."
            ) from error

        if (
            unresolved.exists()
            and unresolved.is_symlink()
        ):
            raise ValueError(
                "Validation target cannot be a symlink."
            )

        return file_path

    def validate_file(
        self,
        path: str,
    ) -> ExecutionResult:
        return _DEVELOPER_VALIDATION_SERVICE.validate_file(
            self,
            path,
        )

    def validate_files(
        self,
        files: list[str],
    ) -> ExecutionResult:
        return _DEVELOPER_VALIDATION_SERVICE.validate_files(
            self,
            files,
        )

    def check_syntax(
        self,
        path: str,
    ) -> ExecutionResult:
        return _DEVELOPER_VALIDATION_SERVICE.check_syntax(
            self,
            path,
        )

    def compile_file(
        self,
        path: str,
    ) -> ExecutionResult:
        return _DEVELOPER_VALIDATION_SERVICE.compile_file(
            self,
            path,
        )

    def run_import_test(
        self,
    ) -> ExecutionResult:
        return _DEVELOPER_VALIDATION_SERVICE.run_import_test(
            self
        )

    def run_test_suite(
        self,
        *,
        changed_files: list[str] | None = None,
        full_suite: bool = True,
    ) -> ExecutionResult:
        return _DEVELOPER_VALIDATION_SERVICE.run_test_suite(
            self,
            changed_files=changed_files,
            full_suite=full_suite,
        )

    def analyze_failure(
        self,
        result: ExecutionResult,
    ) -> dict:
        return _DEVELOPER_VALIDATION_SERVICE.analyze_failure(
            self,
            result,
        )

    def _matching_test_modules(
        self,
        changed_files: list[str],
    ) -> list[str]:
        return _DEVELOPER_VALIDATION_SERVICE._matching_test_modules(
            self,
            changed_files,
        )

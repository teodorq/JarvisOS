from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.autodev.execution_result import ExecutionResult


class DeveloperValidationService:
    """Stateless syntax, import and test execution workflow."""

    def validate_file(
        self,
        validator: Any,
        path: str,
    ) -> ExecutionResult:
        try:
            file_path = validator._resolve_path(
                path
            )
        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="validate_file",
                message=(
                    "Ścieżka pliku nie przeszła "
                    "walidacji bezpieczeństwa."
                ),
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

        if not file_path.exists():
            return ExecutionResult(
                success=False,
                step_name="validate_file",
                message="Plik nie istnieje.",
                data={
                    "path": str(file_path),
                },
                errors=[
                    f"Plik nie istnieje: {file_path}",
                ],
            )

        if not file_path.is_file():
            return ExecutionResult(
                success=False,
                step_name="validate_file",
                message=(
                    "Wskazana ścieżka nie jest plikiem."
                ),
                data={
                    "path": str(file_path),
                },
                errors=[
                    f"Ścieżka nie jest plikiem: {file_path}",
                ],
            )

        syntax_result = validator.check_syntax(
            str(file_path)
        )

        if not syntax_result.success:
            return syntax_result

        compile_result = validator.compile_file(
            str(file_path)
        )

        if not compile_result.success:
            return compile_result

        return ExecutionResult(
            success=True,
            step_name="validate_file",
            message="Plik przeszedł walidację.",
            data={
                "path": str(file_path),
                "syntax": "OK",
                "compile": "OK",
            },
        )

    def validate_files(
        self,
        validator: Any,
        files: list[str],
    ) -> ExecutionResult:
        checked_files = []
        errors = []
        seen_paths = set()

        for path in files:
            try:
                resolved_path = str(
                    validator._resolve_path(
                        path
                    )
                )
            except Exception as error:
                errors.append(
                    f"{type(error).__name__}: {error}"
                )
                continue

            if resolved_path in seen_paths:
                continue

            seen_paths.add(
                resolved_path
            )
            result = validator.validate_file(
                resolved_path
            )
            checked_files.append(
                {
                    "path": resolved_path,
                    "success": result.success,
                    "message": result.message,
                }
            )

            if not result.success:
                errors.extend(
                    result.errors
                )

        return ExecutionResult(
            success=not errors,
            step_name="validate_files",
            message=(
                "Wszystkie pliki są poprawne."
                if not errors
                else "Niektóre pliki zawierają błędy."
            ),
            data={
                "checked_files": checked_files,
                "files_count": len(
                    checked_files
                ),
            },
            errors=errors,
        )

    def check_syntax(
        self,
        validator: Any,
        path: str,
    ) -> ExecutionResult:
        try:
            file_path = validator._resolve_path(
                path
            )
            source = file_path.read_text(
                encoding="utf-8"
            )
            ast.parse(
                source,
                filename=str(file_path),
            )
            return ExecutionResult(
                success=True,
                step_name="check_syntax",
                message="Składnia jest poprawna.",
                data={
                    "path": str(file_path),
                },
            )

        except SyntaxError as error:
            return ExecutionResult(
                success=False,
                step_name="check_syntax",
                message="Wykryto błąd składni.",
                data={
                    "path": str(path),
                    "line": error.lineno or 0,
                    "offset": error.offset or 0,
                },
                errors=[
                    str(error),
                ],
            )

        except UnicodeDecodeError as error:
            return ExecutionResult(
                success=False,
                step_name="check_syntax",
                message=(
                    "Plik nie jest zapisany w UTF-8."
                ),
                data={
                    "path": str(path),
                },
                errors=[
                    str(error),
                ],
            )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="check_syntax",
                message=(
                    "Nie udało się sprawdzić składni."
                ),
                data={
                    "path": str(path),
                },
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

    def compile_file(
        self,
        validator: Any,
        path: str,
    ) -> ExecutionResult:
        try:
            file_path = validator._resolve_path(
                path
            )
            process = validator.process_runner.run(
                [
                    validator.python_executable,
                    "-m",
                    "py_compile",
                    str(file_path),
                ],
                cwd=validator.project_root,
                timeout=20,
            )

            if process.success:
                return ExecutionResult(
                    success=True,
                    step_name="compile_file",
                    message=(
                        "Kompilacja pliku zakończona "
                        "powodzeniem."
                    ),
                    data={
                        "path": str(file_path),
                        "process": process.as_dict(),
                    },
                )

            return self._failed_process_result(
                step_name="compile_file",
                message=(
                    "Kompilacja pliku nie powiodła się."
                ),
                process=process,
                data={
                    "path": str(file_path),
                },
            )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="compile_file",
                message=(
                    "Nie udało się uruchomić kompilacji."
                ),
                data={
                    "path": str(path),
                },
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

    def run_import_test(
        self,
        validator: Any,
    ) -> ExecutionResult:
        try:
            process = validator.process_runner.run(
                [
                    validator.python_executable,
                    "-c",
                    (
                        "from app.gui.main_window "
                        "import MainWindow; "
                        "print('IMPORT OK')"
                    ),
                ],
                cwd=validator.project_root,
                timeout=25,
            )

            if process.success:
                return ExecutionResult(
                    success=True,
                    step_name="run_import_test",
                    message=(
                        "Test importów zakończony "
                        "powodzeniem."
                    ),
                    data={
                        "stdout": (
                            process.stdout.strip()
                        ),
                        "process": process.as_dict(),
                    },
                )

            return self._failed_process_result(
                step_name="run_import_test",
                message=(
                    "Test importów nie powiódł się."
                ),
                process=process,
            )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="run_import_test",
                message=(
                    "Nie udało się uruchomić "
                    "testu importów."
                ),
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

    def run_test_suite(
        self,
        validator: Any,
        *,
        changed_files: list[str] | None = None,
        full_suite: bool = True,
    ) -> ExecutionResult:
        changed_files = list(
            changed_files or []
        )

        if full_suite:
            command = [
                validator.python_executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ]
            mode = "full"

        else:
            test_modules = (
                validator._matching_test_modules(
                    changed_files
                )
            )

            if not test_modules:
                return ExecutionResult(
                    success=True,
                    step_name="run_test_suite",
                    message=(
                        "Nie znaleziono testów "
                        "dopasowanych do zmienionych plików."
                    ),
                    data={
                        "mode": "targeted",
                        "tests": [],
                        "changed_files": changed_files,
                    },
                )

            command = [
                validator.python_executable,
                "-m",
                "unittest",
                *test_modules,
            ]
            mode = "targeted"

        try:
            process = validator.process_runner.run(
                command,
                cwd=validator.project_root,
                timeout=validator.test_timeout,
            )
            process_data = process.as_dict()
            process_data[
                "changed_files"
            ] = changed_files
            process_data[
                "mode"
            ] = mode

            if process.success:
                return ExecutionResult(
                    success=True,
                    step_name="run_test_suite",
                    message=(
                        "Testy zakończone powodzeniem."
                    ),
                    data=process_data,
                )

            return self._failed_process_result(
                step_name="run_test_suite",
                message="Testy nie przeszły.",
                process=process,
                data={
                    "mode": mode,
                    "changed_files": changed_files,
                },
            )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="run_test_suite",
                message=(
                    "Nie udało się uruchomić testów."
                ),
                data={
                    "mode": mode,
                    "changed_files": changed_files,
                },
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

    def analyze_failure(
        self,
        validator: Any,
        result: ExecutionResult,
    ) -> dict:
        errors = [
            str(item)
            for item in result.errors or []
        ]
        data = (
            dict(result.data)
            if isinstance(
                result.data,
                dict,
            )
            else {}
        )
        combined = "\n".join(
            [
                str(result.message),
                *errors,
                str(
                    data.get(
                        "output",
                        "",
                    )
                ),
                str(
                    data.get(
                        "stderr",
                        "",
                    )
                ),
            ]
        ).casefold()
        category = "UNKNOWN"
        retryable = False

        if (
            "syntaxerror" in combined
            or "indentationerror" in combined
            or "błąd składni" in combined
        ):
            category = "SYNTAX"
            retryable = True

        elif (
            "assertionerror" in combined
            or "fail:" in combined
            or "testy nie przeszły" in combined
        ):
            category = "TEST_FAILURE"
            retryable = True

        elif (
            "importerror" in combined
            or "modulenotfounderror" in combined
        ):
            category = "IMPORT"
            retryable = True

        elif (
            "timeout" in combined
            or "przekroczyły limit" in combined
        ):
            category = "TIMEOUT"

        elif (
            "permissionerror" in combined
            or "odmowa dostępu" in combined
        ):
            category = "PERMISSION"

        return {
            "category": category,
            "retryable": retryable,
            "step_name": result.step_name,
            "message": result.message,
            "errors": errors[-10:],
            "data": data,
        }

    def _matching_test_modules(
        self,
        validator: Any,
        changed_files: list[str],
    ) -> list[str]:
        tests_root = (
            validator.project_root
            / "tests"
        )

        if not tests_root.exists():
            return []

        stems = {
            Path(path).stem.casefold()
            for path in changed_files
            if str(path).strip()
        }
        modules: list[str] = []

        for test_path in tests_root.rglob(
            "test_*.py"
        ):
            test_stem = (
                test_path.stem.casefold()
            )

            if not any(
                (
                    stem in test_stem
                    or test_stem.removeprefix(
                        "test_"
                    ) in stem
                )
                for stem in stems
            ):
                continue

            relative = test_path.relative_to(
                validator.project_root
            ).with_suffix(
                ""
            )
            modules.append(
                ".".join(
                    relative.parts
                )
            )

        return sorted(
            set(modules)
        )

    @staticmethod
    def _failed_process_result(
        *,
        step_name: str,
        message: str,
        process,
        data: dict | None = None,
    ) -> ExecutionResult:
        payload = dict(
            data or {}
        )
        payload.update(
            process.as_dict()
        )

        if process.timed_out:
            error = (
                "Proces przekroczył dozwolony "
                "limit czasu."
            )
        else:
            error = (
                process.stderr.strip()
                or process.stdout.strip()
                or "Proces zwrócił błąd."
            )

        return ExecutionResult(
            success=False,
            step_name=step_name,
            message=message,
            data=payload,
            errors=[
                error,
            ],
        )

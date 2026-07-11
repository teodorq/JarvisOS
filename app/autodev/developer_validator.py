import ast
import subprocess
import sys
from pathlib import Path

from app.autodev.execution_result import ExecutionResult


class DeveloperValidator:

    def __init__(self, project_root="C:/JarvisAI"):
        self.project_root = Path(project_root).resolve()
        self.python_executable = sys.executable

    def _resolve_path(self, path: str) -> Path:
        file_path = Path(path)

        if not file_path.is_absolute():
            file_path = self.project_root / file_path

        return file_path.resolve()

    def validate_file(self, path: str) -> ExecutionResult:
        file_path = self._resolve_path(path)

        if not file_path.exists():
            return ExecutionResult(
                success=False,
                step_name="validate_file",
                message="Plik nie istnieje.",
                data={
                    "path": str(file_path)
                },
                errors=[
                    f"Plik nie istnieje: {file_path}"
                ]
            )

        if not file_path.is_file():
            return ExecutionResult(
                success=False,
                step_name="validate_file",
                message="Wskazana ścieżka nie jest plikiem.",
                data={
                    "path": str(file_path)
                },
                errors=[
                    f"Ścieżka nie jest plikiem: {file_path}"
                ]
            )

        syntax_result = self.check_syntax(str(file_path))

        if not syntax_result.success:
            return syntax_result

        compile_result = self.compile_file(str(file_path))

        if not compile_result.success:
            return compile_result

        return ExecutionResult(
            success=True,
            step_name="validate_file",
            message="Plik przeszedł walidację.",
            data={
                "path": str(file_path),
                "syntax": "OK",
                "compile": "OK"
            }
        )

    def validate_files(self, files: list[str]) -> ExecutionResult:
        checked_files = []
        errors = []
        seen_paths = set()

        for path in files:
            resolved_path = str(self._resolve_path(path))

            if resolved_path in seen_paths:
                continue

            seen_paths.add(resolved_path)
            result = self.validate_file(resolved_path)

            checked_files.append({
                "path": resolved_path,
                "success": result.success,
                "message": result.message
            })

            if not result.success:
                errors.extend(result.errors)

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
                "files_count": len(checked_files)
            },
            errors=errors
        )

    def check_syntax(self, path: str) -> ExecutionResult:
        file_path = self._resolve_path(path)

        try:
            source = file_path.read_text(
                encoding="utf-8"
            )

            ast.parse(
                source,
                filename=str(file_path)
            )

            return ExecutionResult(
                success=True,
                step_name="check_syntax",
                message="Składnia jest poprawna.",
                data={
                    "path": str(file_path)
                }
            )

        except SyntaxError as error:
            return ExecutionResult(
                success=False,
                step_name="check_syntax",
                message="Wykryto błąd składni.",
                data={
                    "path": str(file_path),
                    "line": error.lineno or 0,
                    "offset": error.offset or 0
                },
                errors=[
                    str(error)
                ]
            )

        except UnicodeDecodeError as error:
            return ExecutionResult(
                success=False,
                step_name="check_syntax",
                message="Plik nie jest zapisany w UTF-8.",
                data={
                    "path": str(file_path)
                },
                errors=[
                    str(error)
                ]
            )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="check_syntax",
                message="Nie udało się sprawdzić składni.",
                data={
                    "path": str(file_path)
                },
                errors=[
                    str(error)
                ]
            )

    def compile_file(self, path: str) -> ExecutionResult:
        file_path = self._resolve_path(path)

        try:
            result = subprocess.run(
                [
                    self.python_executable,
                    "-m",
                    "py_compile",
                    str(file_path)
                ],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=20
            )

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    step_name="compile_file",
                    message="Kompilacja pliku zakończona powodzeniem.",
                    data={
                        "path": str(file_path),
                        "python": self.python_executable
                    }
                )

            return ExecutionResult(
                success=False,
                step_name="compile_file",
                message="Kompilacja pliku nie powiodła się.",
                data={
                    "path": str(file_path),
                    "stdout": result.stdout,
                    "python": self.python_executable
                },
                errors=[
                    result.stderr or "Nieznany błąd kompilacji."
                ]
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                step_name="compile_file",
                message="Przekroczono czas kompilacji.",
                data={
                    "path": str(file_path)
                },
                errors=[
                    "Timeout po 20 sekundach."
                ]
            )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="compile_file",
                message="Nie udało się uruchomić kompilacji.",
                data={
                    "path": str(file_path)
                },
                errors=[
                    str(error)
                ]
            )

    def run_import_test(self) -> ExecutionResult:
        try:
            result = subprocess.run(
                [
                    self.python_executable,
                    "-c",
                    (
                        "from app.gui.main_window "
                        "import MainWindow; "
                        "print('IMPORT OK')"
                    )
                ],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=25
            )

            if result.returncode == 0:
                return ExecutionResult(
                    success=True,
                    step_name="run_import_test",
                    message="Test importów zakończony powodzeniem.",
                    data={
                        "stdout": result.stdout.strip(),
                        "python": self.python_executable
                    }
                )

            return ExecutionResult(
                success=False,
                step_name="run_import_test",
                message="Test importów nie powiódł się.",
                data={
                    "stdout": result.stdout,
                    "python": self.python_executable
                },
                errors=[
                    result.stderr or "Nieznany błąd importu."
                ]
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                step_name="run_import_test",
                message="Test importów przekroczył limit czasu.",
                errors=[
                    "Timeout po 25 sekundach."
                ]
            )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="run_import_test",
                message="Nie udało się uruchomić testu importów.",
                errors=[
                    str(error)
                ]
            )

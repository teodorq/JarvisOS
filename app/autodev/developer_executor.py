from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import os
import stat
import tempfile
import time
from pathlib import Path

from app.autodev.backup_bundle import BackupBundleManager
from app.autodev.change_transaction import ChangeTransaction
from app.autodev.developer_validator import DeveloperValidator
from app.autodev.execution_result import ExecutionResult
from app.autodev.rollback_manager import RollbackManager


class DeveloperExecutor:

    def __init__(
        self,
        project_root=default_project_root(),
        run_tests: bool = True,
        full_test_suite: bool = True,
        test_timeout: int = 180,
    ):
        self.project_root = Path(project_root).expanduser().resolve()
        self.run_tests = bool(run_tests)
        self.full_test_suite = bool(full_test_suite)

        self.backups = BackupBundleManager(
            project_root=self.project_root
        )
        self.validator = DeveloperValidator(
            project_root=str(self.project_root),
            test_timeout=test_timeout,
        )
        self.rollback_manager = RollbackManager(
            project_root=self.project_root,
            backups=self.backups,
        )

        self.last_transaction = None
        self.last_result = None

    def execute(
        self,
        transaction: ChangeTransaction,
        auto_rollback: bool = True
    ) -> ExecutionResult:
        started_at = time.perf_counter()
        self.last_transaction = transaction

        path_errors = self._prepare_transaction_paths(transaction)

        if path_errors:
            transaction.mark_failed()
            return self._finish_result(
                ExecutionResult(
                    success=False,
                    step_name="path_validation",
                    message="Ścieżki transakcji są niepoprawne.",
                    data={
                        "transaction": transaction.summary()
                    },
                    errors=path_errors
                ),
                started_at
            )

        valid, validation_errors = transaction.validate()

        if not valid:
            transaction.mark_failed()

            return self._finish_result(
                ExecutionResult(
                    success=False,
                    step_name="transaction_validation",
                    message="Transakcja jest niepoprawna.",
                    data={
                        "transaction": transaction.summary()
                    },
                    errors=validation_errors
                ),
                started_at
            )

        backup_result = self._create_backup(transaction)

        if not backup_result.success:
            transaction.mark_failed()
            return self._finish_result(backup_result, started_at)

        apply_result = self._apply_changes(transaction)

        if not apply_result.success:
            if auto_rollback:
                self._attach_rollback(apply_result, transaction)

            return self._finish_result(apply_result, started_at)

        validation_result = self._validate_transaction(transaction)

        if not validation_result.success:
            if auto_rollback:
                self._attach_rollback(validation_result, transaction)

            return self._finish_result(validation_result, started_at)

        transaction.mark_validated()

        return self._finish_result(
            ExecutionResult(
                success=True,
                step_name="developer_executor",
                message=(
                    "Zmiany zostały zapisane "
                    "i przeszły walidację."
                ),
                data={
                    "transaction": transaction.summary(),
                    "backup_bundle": transaction.backup_bundle_path,
                    "changed_files": transaction.files(),
                    "rollback_available": bool(
                        transaction.backup_bundle_path
                    ),
                    "tests_enabled": self.run_tests,
                    "full_test_suite": self.full_test_suite,
                }
            ),
            started_at
        )

    def rollback_last(self) -> ExecutionResult:
        if self.last_transaction is None:
            result = ExecutionResult(
                success=False,
                step_name="rollback_last",
                message=(
                    "Brak ostatniej transakcji "
                    "do cofnięcia."
                ),
                errors=[
                    "Nie wykonano jeszcze żadnej transakcji."
                ]
            )
            self.last_result = result
            return result

        transaction = self.last_transaction
        primary_errors: list[str] = []

        try:
            primary_result = (
                self.rollback_manager.rollback(
                    transaction
                )
            )

            if primary_result.success:
                self.last_result = primary_result
                return primary_result

            primary_errors.extend(
                primary_result.errors
            )

        except Exception as error:
            primary_errors.append(
                "Rollback manager error: "
                f"{type(error).__name__}: {error}"
            )

        fallback_result = (
            self._restore_transaction_snapshot(
                transaction
            )
        )

        if primary_errors:
            fallback_result.data.setdefault(
                "primary_rollback_errors",
                list(
                    primary_errors
                ),
            )

        self.last_result = fallback_result
        return fallback_result

    def preview(
        self,
        transaction: ChangeTransaction
    ) -> str:
        lines = [
            "AUTODEV TRANSACTION PREVIEW",
            f"Cel: {transaction.goal}",
            f"Target: {transaction.target or 'brak'}",
            f"Pliki: {len(transaction.changes)}",
            ""
        ]

        for change in transaction.changes:
            lines.append(f"PLIK: {change.path}")
            lines.append("")
            lines.append("STARA WERSJA:")
            lines.append(change.old_content)
            lines.append("")
            lines.append("NOWA WERSJA:")
            lines.append(change.new_content)
            lines.append("")
            lines.append("=" * 60)

        return "\n".join(lines)

    def _prepare_transaction_paths(
        self,
        transaction: ChangeTransaction,
    ) -> list[str]:
        errors: list[str] = []
        seen_paths: set[str] = set()

        for change in transaction.changes:
            raw_path = str(
                change.path
            ).strip()

            if not raw_path:
                errors.append(
                    "Zmiana zawiera pustą ścieżkę pliku."
                )
                continue

            creates_file = self._is_creation(
                change
            )

            try:
                resolved = (
                    self._resolve_transaction_file(
                        raw_path,
                        allow_missing=creates_file,
                    )
                )

                if (
                    creates_file
                    and resolved.exists()
                ):
                    raise FileExistsError(
                        "Plik przeznaczony do utworzenia "
                        f"już istnieje: {resolved}"
                    )

            except Exception as error:
                errors.append(
                    f"{raw_path}: "
                    f"{type(error).__name__}: {error}"
                )
                continue

            normalized = os.path.normcase(
                str(resolved)
            )

            if normalized in seen_paths:
                errors.append(
                    "Plik występuje kilka razy: "
                    f"{raw_path}"
                )
                continue

            seen_paths.add(
                normalized
            )
            change.path = str(
                resolved
            )

        return errors

    def _resolve_active_file(
        self,
        raw_path: str | Path,
    ) -> Path:
        return self._resolve_transaction_file(
            raw_path,
            allow_missing=False,
        )

    def _resolve_transaction_file(
        self,
        raw_path: str | Path,
        *,
        allow_missing: bool,
    ) -> Path:
        candidate = Path(
            raw_path
        ).expanduser()

        if not candidate.is_absolute():
            candidate = (
                self.project_root
                / candidate
            )

        if candidate.is_symlink():
            raise OSError(
                "Dowiązania symboliczne nie są "
                f"dozwolone: {candidate}"
            )

        resolved = candidate.resolve(
            strict=not allow_missing
        )

        try:
            resolved.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Plik znajduje się poza "
                "katalogiem projektu."
            ) from error

        current = candidate

        while current != self.project_root:
            if (
                current.exists()
                and current.is_symlink()
            ):
                raise OSError(
                    "Ścieżka zawiera dowiązanie: "
                    f"{current}"
                )

            parent = current.parent

            if parent == current:
                break

            current = parent

        if resolved.exists():
            if not resolved.is_file():
                raise FileNotFoundError(
                    f"To nie jest plik: {resolved}"
                )
        elif not allow_missing:
            raise FileNotFoundError(
                f"Plik nie istnieje: {resolved}"
            )
        else:
            existing_parent = resolved.parent

            while (
                existing_parent != self.project_root
                and not existing_parent.exists()
            ):
                existing_parent = (
                    existing_parent.parent
                )

            if (
                not existing_parent.exists()
                or not existing_parent.is_dir()
            ):
                raise FileNotFoundError(
                    "Nie znaleziono bezpiecznego "
                    f"katalogu nadrzędnego: {resolved}"
                )

            try:
                existing_parent.relative_to(
                    self.project_root
                )
            except ValueError as error:
                raise ValueError(
                    "Katalog nadrzędny znajduje się "
                    "poza projektem."
                ) from error

        return resolved


    @staticmethod
    def _is_creation(
        change: object,
    ) -> bool:
        return (
            str(
                getattr(
                    change,
                    "operation",
                    "update",
                )
            )
            .strip()
            .casefold()
            == "create"
        )

    def _create_backup(
        self,
        transaction: ChangeTransaction,
    ) -> ExecutionResult:
        existing_files = (
            transaction.existing_files()
        )
        manifest = self.backups.create_bundle(
            files=existing_files,
            goal=transaction.goal,
        )
        bundle_path = manifest.get(
            "bundle_path",
            "",
        )
        files = manifest.get(
            "files",
            [],
        )
        errors = manifest.get(
            "errors",
            [],
        )
        expected_files = len(
            existing_files
        )

        if (
            errors
            or len(files)
            != expected_files
        ):
            return ExecutionResult(
                success=False,
                step_name="create_backup",
                message=(
                    "Nie udało się przygotować "
                    "pełnego backupu."
                ),
                data={
                    "bundle_path": bundle_path,
                    "backed_up_files": len(files),
                    "expected_files": expected_files,
                    "new_files": len(
                        transaction.created_files()
                    ),
                },
                errors=errors or [
                    "Nie wszystkie istniejące pliki "
                    "zostały zapisane."
                ],
            )

        transaction.mark_backed_up(
            bundle_path
        )

        return ExecutionResult(
            success=True,
            step_name="create_backup",
            message=(
                "Utworzono backup istniejących "
                "plików transakcji."
            ),
            data={
                "bundle_path": bundle_path,
                "files_count": len(files),
                "new_files_count": len(
                    transaction.created_files()
                ),
            },
        )

    def _apply_changes(
        self,
        transaction: ChangeTransaction,
    ) -> ExecutionResult:
        prepared: list[
            tuple[object, Path, bool]
        ] = []

        for change in transaction.changes:
            creates_file = self._is_creation(
                change
            )

            try:
                file_path = (
                    self._resolve_transaction_file(
                        change.path,
                        allow_missing=creates_file,
                    )
                )

                if creates_file:
                    if file_path.exists():
                        raise FileExistsError(
                            "Plik został utworzony "
                            "po przygotowaniu transakcji."
                        )
                else:
                    current_content = (
                        file_path.read_text(
                            encoding="utf-8"
                        )
                    )

                    if (
                        current_content
                        != change.old_content
                    ):
                        raise RuntimeError(
                            "Zawartość pliku zmieniła się "
                            "od momentu utworzenia planu."
                        )

                prepared.append(
                    (
                        change,
                        file_path,
                        creates_file,
                    )
                )

            except Exception as error:
                change.status = "failed"
                change.error = str(error)
                transaction.mark_failed()

                return ExecutionResult(
                    success=False,
                    step_name="apply_changes",
                    message=(
                        "Walidacja przed zapisem "
                        "nie powiodła się."
                    ),
                    data={
                        "changed_files": [],
                        "failed_file": change.path,
                    },
                    errors=[
                        f"{type(error).__name__}: {error}",
                    ],
                )

        transaction.mark_applying()
        changed_files: list[str] = []

        for (
            change,
            prepared_path,
            creates_file,
        ) in prepared:
            try:
                file_path = (
                    self._resolve_transaction_file(
                        prepared_path,
                        allow_missing=creates_file,
                    )
                )

                if file_path != prepared_path:
                    raise RuntimeError(
                        "Ścieżka pliku zmieniła się "
                        "przed zapisem."
                    )

                if creates_file:
                    if file_path.exists():
                        raise FileExistsError(
                            "Plik pojawił się "
                            "bezpośrednio przed zapisem."
                        )

                    file_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    verified_path = (
                        self._resolve_transaction_file(
                            file_path,
                            allow_missing=True,
                        )
                    )

                    if verified_path != file_path:
                        raise RuntimeError(
                            "Katalog docelowy zmienił się "
                            "przed zapisem."
                        )
                else:
                    current_content = (
                        file_path.read_text(
                            encoding="utf-8"
                        )
                    )

                    if (
                        current_content
                        != change.old_content
                    ):
                        raise RuntimeError(
                            "Zawartość pliku zmieniła się "
                            "bezpośrednio przed zapisem."
                        )

                self._atomic_write_text(
                    file_path,
                    change.new_content,
                )
                change.status = "applied"
                change.error = ""
                changed_files.append(
                    change.path
                )

            except Exception as error:
                change.status = "failed"
                change.error = str(error)
                transaction.mark_failed()

                return ExecutionResult(
                    success=False,
                    step_name="apply_changes",
                    message=(
                        "Nie udało się atomowo "
                        "zapisać wszystkich zmian."
                    ),
                    data={
                        "changed_files": changed_files,
                        "failed_file": change.path,
                    },
                    errors=[
                        f"{type(error).__name__}: {error}",
                    ],
                )

        transaction.mark_applied()

        return ExecutionResult(
            success=True,
            step_name="apply_changes",
            message=(
                "Zapisano wszystkie zmiany "
                "atomowo na poziomie plików."
            ),
            data={
                "changed_files": changed_files,
                "created_files": (
                    transaction.created_files()
                ),
            },
        )

    def _atomic_write_text(
        self,
        file_path: Path,
        content: str,
    ) -> None:
        file_mode = (
            stat.S_IMODE(
                file_path.stat().st_mode
            )
            if file_path.exists()
            else 0o644
        )
        temporary_path = None
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=file_path.parent,
                prefix=f".{file_path.name}.",
                suffix=".autodev.tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(
                    content
                )
                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )
                temporary_path = Path(
                    temporary_file.name
                )

            os.chmod(
                temporary_path,
                file_mode,
            )
            self._replace_with_retry(
                temporary_path,
                file_path,
            )
            temporary_path = None

        finally:
            if temporary_path is not None:
                temporary_path.unlink(
                    missing_ok=True
                )

    def _validate_transaction(
        self,
        transaction: ChangeTransaction
    ) -> ExecutionResult:
        files_result = self.validator.validate_files(
            transaction.files()
        )

        if not files_result.success:
            transaction.mark_failed()
            return files_result

        import_result = self.validator.run_import_test()

        if not import_result.success:
            transaction.mark_failed()
            return import_result

        tests_result = None

        if self.run_tests:
            tests_result = self.validator.run_test_suite(
                changed_files=transaction.files(),
                full_suite=self.full_test_suite,
            )

            if not tests_result.success:
                transaction.mark_failed()
                return tests_result

        return ExecutionResult(
            success=True,
            step_name="validate_transaction",
            message=(
                "Walidacja transakcji "
                "zakończona powodzeniem."
            ),
            data={
                "files": files_result.as_dict(),
                "imports": import_result.as_dict(),
                "tests": (
                    tests_result.as_dict()
                    if tests_result is not None
                    else {
                        "success": True,
                        "status": "SKIPPED",
                    }
                ),
            }
        )

    def _attach_rollback(
        self,
        result: ExecutionResult,
        transaction: ChangeTransaction
    ) -> None:
        primary_errors: list[str] = []

        try:
            rollback_result = self.rollback_manager.rollback(
                transaction
            )

            if rollback_result.success:
                result.data["rollback"] = (
                    rollback_result.as_dict()
                )
                return

            primary_errors.extend(
                rollback_result.errors
            )

        except Exception as error:
            primary_errors.append(
                "Rollback manager error: "
                f"{type(error).__name__}: {error}"
            )

        fallback_result = (
            self._restore_transaction_snapshot(
                transaction
            )
        )
        fallback_data = fallback_result.as_dict()

        if primary_errors:
            fallback_data.setdefault(
                "data",
                {},
            )["primary_rollback_errors"] = list(
                primary_errors
            )

        result.data["rollback"] = fallback_data

        if not fallback_result.success:
            for error in (
                primary_errors
                + fallback_result.errors
            ):
                if error not in result.errors:
                    result.errors.append(
                        error
                    )

    def _restore_transaction_snapshot(
        self,
        transaction: ChangeTransaction,
    ) -> ExecutionResult:
        prepared: list[
            tuple[object, Path, bool]
        ] = []

        try:
            for change in transaction.changes:
                creates_file = self._is_creation(
                    change
                )
                file_path = (
                    self._resolve_transaction_file(
                        change.path,
                        allow_missing=creates_file,
                    )
                )
                prepared.append(
                    (
                        change,
                        file_path,
                        creates_file,
                    )
                )
        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="rollback_fallback",
                message=(
                    "Awaryjny rollback nie przeszedł "
                    "walidacji ścieżek."
                ),
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

        restored: list[str] = []
        removed: list[str] = []

        try:
            for (
                change,
                file_path,
                creates_file,
            ) in reversed(prepared):
                if creates_file:
                    if file_path.exists():
                        if not file_path.is_file():
                            raise ValueError(
                                "Nowy target nie jest plikiem: "
                                f"{file_path}"
                            )

                        file_path.unlink()

                    removed.append(
                        str(file_path)
                    )
                    self._remove_empty_parents(
                        file_path.parent
                    )
                else:
                    DeveloperExecutor._atomic_write_text(
                        self,
                        file_path,
                        change.old_content,
                    )
                    restored.append(
                        str(file_path)
                    )

        except Exception as error:
            return ExecutionResult(
                success=False,
                step_name="rollback_fallback",
                message=(
                    "Awaryjne przywracanie plików "
                    "nie powiodło się."
                ),
                data={
                    "restored": restored,
                    "removed_created_files": removed,
                },
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

        transaction.mark_rolled_back()

        for change in transaction.changes:
            change.status = "rolled_back"
            change.error = ""

        return ExecutionResult(
            success=True,
            step_name="rollback_fallback",
            message=(
                "Przywrócono istniejące pliki "
                "i usunięto nowe pliki z lokalnego "
                "snapshotu transakcji."
            ),
            data={
                "restored": restored,
                "removed_created_files": removed,
                "fallback": True,
            },
        )

    def _remove_empty_parents(
        self,
        directory: Path,
    ) -> None:
        current = directory

        while (
            current != self.project_root
            and current.is_relative_to(
                self.project_root
            )
        ):
            try:
                current.rmdir()
            except OSError:
                break

            current = current.parent

    @staticmethod
    def _replace_with_retry(
        source: Path,
        destination: Path,
        *,
        attempts: int = 6,
    ) -> None:
        last_error: OSError | None = None

        for attempt in range(
            max(
                1,
                attempts,
            )
        ):
            try:
                if destination.exists():
                    try:
                        current_mode = stat.S_IMODE(
                            destination.stat().st_mode
                        )
                        os.chmod(
                            destination,
                            current_mode
                            | stat.S_IWRITE,
                        )
                    except OSError:
                        raise RuntimeError("AutoDev: przechwycony wyjątek")

                os.replace(
                    source,
                    destination,
                )
                return

            except OSError as error:
                last_error = error

                if attempt + 1 >= attempts:
                    break

                time.sleep(
                    0.02
                    * (attempt + 1)
                )

        if last_error is not None:
            raise last_error

    def _finish_result(
        self,
        result: ExecutionResult,
        started_at: float
    ) -> ExecutionResult:
        result.data.setdefault(
            "duration_seconds",
            round(time.perf_counter() - started_at, 6)
        )
        self.last_result = result
        return result

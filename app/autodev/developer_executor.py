from __future__ import annotations

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

    def __init__(self, project_root="C:/JarvisAI"):
        self.project_root = Path(project_root).expanduser().resolve()

        self.backups = BackupBundleManager()
        self.validator = DeveloperValidator(
            project_root=str(self.project_root)
        )
        self.rollback_manager = RollbackManager()

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
                    )
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

        result = self.rollback_manager.rollback(
            self.last_transaction
        )
        self.last_result = result
        return result

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
        transaction: ChangeTransaction
    ) -> list[str]:
        errors = []
        seen_paths = set()

        for change in transaction.changes:
            raw_path = str(change.path).strip()

            if not raw_path:
                errors.append("Zmiana zawiera pustą ścieżkę pliku.")
                continue

            candidate = Path(raw_path).expanduser()

            if not candidate.is_absolute():
                candidate = self.project_root / candidate

            resolved = candidate.resolve()

            try:
                resolved.relative_to(self.project_root)
            except ValueError:
                errors.append(
                    "Plik znajduje się poza katalogiem projektu: "
                    f"{raw_path}"
                )
                continue

            normalized = os.path.normcase(str(resolved))

            if normalized in seen_paths:
                errors.append(
                    f"Plik występuje kilka razy: {raw_path}"
                )
                continue

            seen_paths.add(normalized)
            change.path = str(resolved)

        return errors

    def _create_backup(
        self,
        transaction: ChangeTransaction
    ) -> ExecutionResult:
        manifest = self.backups.create_bundle(
            files=transaction.files(),
            goal=transaction.goal
        )

        bundle_path = manifest.get("bundle_path", "")
        files = manifest.get("files", [])
        errors = manifest.get("errors", [])

        if errors or len(files) != len(transaction.changes):
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
                    "expected_files": len(transaction.changes)
                },
                errors=errors or [
                    "Nie wszystkie pliki zostały zapisane."
                ]
            )

        transaction.mark_backed_up(bundle_path)

        return ExecutionResult(
            success=True,
            step_name="create_backup",
            message="Utworzono backup transakcji.",
            data={
                "bundle_path": bundle_path,
                "files_count": len(files)
            }
        )

    def _apply_changes(
        self,
        transaction: ChangeTransaction
    ) -> ExecutionResult:
        transaction.mark_applying()
        changed_files = []

        for change in transaction.changes:
            file_path = Path(change.path)

            try:
                if not file_path.is_file():
                    raise FileNotFoundError(
                        f"Plik nie istnieje: {file_path}"
                    )

                current_content = file_path.read_text(
                    encoding="utf-8"
                )

                if current_content != change.old_content:
                    change.status = "failed"
                    change.error = (
                        "Zawartość pliku zmieniła się "
                        "od momentu utworzenia planu."
                    )
                    transaction.mark_failed()

                    return ExecutionResult(
                        success=False,
                        step_name="apply_changes",
                        message="Przerwano zapis zmian.",
                        data={
                            "changed_files": changed_files,
                            "failed_file": change.path
                        },
                        errors=[change.error]
                    )

                self._atomic_write_text(
                    file_path,
                    change.new_content
                )

                change.status = "applied"
                change.error = ""
                changed_files.append(change.path)

            except Exception as error:
                change.status = "failed"
                change.error = str(error)
                transaction.mark_failed()

                return ExecutionResult(
                    success=False,
                    step_name="apply_changes",
                    message="Nie udało się zapisać zmian.",
                    data={
                        "changed_files": changed_files,
                        "failed_file": change.path
                    },
                    errors=[str(error)]
                )

        transaction.mark_applied()

        return ExecutionResult(
            success=True,
            step_name="apply_changes",
            message="Zapisano wszystkie zmiany.",
            data={
                "changed_files": changed_files
            }
        )

    def _atomic_write_text(
        self,
        file_path: Path,
        content: str
    ) -> None:
        file_mode = stat.S_IMODE(file_path.stat().st_mode)
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=file_path.parent,
                prefix=f".{file_path.name}.",
                suffix=".autodev.tmp",
                delete=False
            ) as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)

            os.chmod(temporary_path, file_mode)
            os.replace(temporary_path, file_path)
            temporary_path = None

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

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

        return ExecutionResult(
            success=True,
            step_name="validate_transaction",
            message=(
                "Walidacja transakcji "
                "zakończona powodzeniem."
            ),
            data={
                "files": files_result.as_dict(),
                "imports": import_result.as_dict()
            }
        )

    def _attach_rollback(
        self,
        result: ExecutionResult,
        transaction: ChangeTransaction
    ) -> None:
        try:
            rollback_result = self.rollback_manager.rollback(
                transaction
            )
            result.data.setdefault(
                "rollback",
                rollback_result.as_dict()
            )

            if not rollback_result.success:
                result.errors.extend(
                    error
                    for error in rollback_result.errors
                    if error not in result.errors
                )

        except Exception as error:
            result.data.setdefault(
                "rollback",
                {
                    "success": False,
                    "step_name": "rollback",
                    "message": "Rollback zgłosił wyjątek.",
                    "errors": [str(error)]
                }
            )
            result.errors.append(
                f"Rollback error: {type(error).__name__}: {error}"
            )

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

from __future__ import annotations

from pathlib import Path

from app.autodev.backup_bundle import BackupBundleManager
from app.autodev.change_transaction import ChangeTransaction
from app.autodev.execution_result import ExecutionResult


class RollbackManager:

    def __init__(
        self,
        project_root: str | Path | None = None,
        backups: BackupBundleManager | None = None,
    ) -> None:
        self.backups = (
            backups
            or BackupBundleManager(
                project_root=project_root
            )
        )
        self.project_root = (
            self.backups.project_root
        )

    def rollback(
        self,
        transaction: ChangeTransaction,
    ) -> ExecutionResult:
        update_changes = [
            change
            for change in transaction.changes
            if not change.creates_file
        ]
        create_changes = [
            change
            for change in transaction.changes
            if change.creates_file
        ]

        restored: list[str] = []
        verified: list[str] = []
        removed: list[str] = []
        errors: list[str] = []

        if update_changes:
            if not transaction.backup_bundle_path:
                errors.append(
                    "Transakcja nie ma backupu "
                    "dla aktualizowanych plików."
                )
            else:
                restore_result = (
                    self.backups.restore_bundle(
                        transaction.backup_bundle_path
                    )
                )
                restored.extend(
                    restore_result.get(
                        "restored",
                        [],
                    )
                )
                verified.extend(
                    restore_result.get(
                        "verified",
                        [],
                    )
                )

                if not restore_result.get(
                    "success",
                    False,
                ):
                    errors.extend(
                        restore_result.get(
                            "errors",
                            [],
                        )
                    )

        if not errors:
            for change in reversed(
                create_changes
            ):
                try:
                    target = (
                        self._resolve_created_target(
                            change.path
                        )
                    )

                    if target.exists():
                        if not target.is_file():
                            raise ValueError(
                                "Cel nowego pliku nie jest "
                                f"zwykłym plikiem: {target}"
                            )

                        target.unlink()

                    removed.append(
                        str(target)
                    )
                    self._remove_empty_parents(
                        target.parent
                    )

                except Exception as error:
                    errors.append(
                        "Nie udało się usunąć "
                        f"nowego pliku {change.path}: "
                        f"{type(error).__name__}: {error}"
                    )

        success = not errors

        if success:
            transaction.mark_rolled_back()

            for change in transaction.changes:
                change.status = "rolled_back"
                change.error = ""

            return ExecutionResult(
                success=True,
                step_name="rollback",
                message=(
                    "Przywrócono istniejące pliki "
                    "i usunięto pliki utworzone "
                    "przez transakcję."
                ),
                data={
                    "bundle_path": (
                        transaction.backup_bundle_path
                    ),
                    "restored": restored,
                    "verified": verified,
                    "removed_created_files": removed,
                },
            )

        transaction.mark_failed()

        return ExecutionResult(
            success=False,
            step_name="rollback",
            message=(
                "Rollback nie powiódł się. "
                "Nie zastosowano niezweryfikowanego wyniku."
            ),
            data={
                "bundle_path": (
                    transaction.backup_bundle_path
                ),
                "restored": restored,
                "verified": verified,
                "removed_created_files": removed,
            },
            errors=errors,
        )

    def _resolve_created_target(
        self,
        raw_path: str | Path,
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
            raise ValueError(
                "Nowy plik jest dowiązaniem symbolicznym."
            )

        resolved = candidate.resolve(
            strict=False
        )

        try:
            resolved.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Nowy plik znajduje się poza projektem."
            ) from error

        current = candidate

        while current != self.project_root:
            if (
                current.exists()
                and current.is_symlink()
            ):
                raise ValueError(
                    "Ścieżka nowego pliku zawiera "
                    "dowiązanie symboliczne."
                )

            parent = current.parent

            if parent == current:
                break

            current = parent

        return resolved

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

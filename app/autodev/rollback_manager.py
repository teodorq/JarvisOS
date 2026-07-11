from app.autodev.backup_bundle import BackupBundleManager
from app.autodev.change_transaction import ChangeTransaction
from app.autodev.execution_result import ExecutionResult


class RollbackManager:

    def __init__(self):
        self.backups = BackupBundleManager()

    def rollback(
        self,
        transaction: ChangeTransaction
    ) -> ExecutionResult:

        if not transaction.backup_bundle_path:
            return ExecutionResult(
                success=False,
                step_name="rollback",
                message="Transakcja nie ma backupu.",
                data={
                    "status": transaction.status
                },
                errors=[
                    "Brak ścieżki do backupu."
                ]
            )

        restore_result = self.backups.restore_bundle(
            transaction.backup_bundle_path
        )

        success = restore_result.get(
            "success",
            False
        )

        if success:
            transaction.mark_rolled_back()

            for change in transaction.changes:
                change.status = "rolled_back"

            return ExecutionResult(
                success=True,
                step_name="rollback",
                message="Przywrócono pliki z backupu.",
                data={
                    "bundle_path": (
                        transaction.backup_bundle_path
                    ),
                    "restored": restore_result.get(
                        "restored",
                        []
                    )
                }
            )

        transaction.mark_failed()

        return ExecutionResult(
            success=False,
            step_name="rollback",
            message="Rollback nie powiódł się.",
            data={
                "bundle_path": (
                    transaction.backup_bundle_path
                ),
                "restored": restore_result.get(
                    "restored",
                    []
                )
            },
            errors=restore_result.get(
                "errors",
                []
            )
        )
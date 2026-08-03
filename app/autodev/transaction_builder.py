from __future__ import annotations

from pathlib import Path

from app.autodev.change_transaction import (
    ChangeTransaction,
)


class TransactionBuilder:

    def build_file_replacement(
        self,
        goal: str,
        target: str,
        path: str,
        new_content: str,
    ) -> ChangeTransaction:
        file_path = Path(
            path
        )

        if not file_path.exists():
            raise FileNotFoundError(
                f"Plik nie istnieje: {file_path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"Ścieżka nie jest plikiem: {file_path}"
            )

        old_content = file_path.read_text(
            encoding="utf-8"
        )
        transaction = ChangeTransaction(
            goal=goal,
            target=target,
        )
        transaction.add_change(
            path=str(file_path),
            old_content=old_content,
            new_content=new_content,
            operation="update",
        )
        return transaction

    def build_multi_file_replacement(
        self,
        goal: str,
        target: str,
        replacements: dict[str, str],
        *,
        allow_create: bool = False,
    ) -> ChangeTransaction:
        transaction = ChangeTransaction(
            goal=goal,
            target=target,
        )

        for path, new_content in replacements.items():
            file_path = Path(
                path
            )

            if file_path.exists():
                if not file_path.is_file():
                    raise ValueError(
                        "Ścieżka nie jest plikiem: "
                        f"{file_path}"
                    )

                old_content = file_path.read_text(
                    encoding="utf-8"
                )
                operation = "update"
            elif allow_create:
                old_content = ""
                operation = "create"
            else:
                raise FileNotFoundError(
                    f"Plik nie istnieje: {file_path}"
                )

            transaction.add_change(
                path=str(file_path),
                old_content=old_content,
                new_content=new_content,
                operation=operation,
            )

        return transaction

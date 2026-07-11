from pathlib import Path

from app.autodev.change_transaction import ChangeTransaction


class TransactionBuilder:

    def build_file_replacement(
        self,
        goal: str,
        target: str,
        path: str,
        new_content: str
    ) -> ChangeTransaction:

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Plik nie istnieje: {file_path}"
            )

        old_content = file_path.read_text(
            encoding="utf-8"
        )

        transaction = ChangeTransaction(
            goal=goal,
            target=target
        )

        transaction.add_change(
            path=str(file_path),
            old_content=old_content,
            new_content=new_content
        )

        return transaction

    def build_multi_file_replacement(
        self,
        goal: str,
        target: str,
        replacements: dict[str, str]
    ) -> ChangeTransaction:

        transaction = ChangeTransaction(
            goal=goal,
            target=target
        )

        for path, new_content in replacements.items():
            file_path = Path(path)

            if not file_path.exists():
                raise FileNotFoundError(
                    f"Plik nie istnieje: {file_path}"
                )

            old_content = file_path.read_text(
                encoding="utf-8"
            )

            transaction.add_change(
                path=str(file_path),
                old_content=old_content,
                new_content=new_content
            )

        return transaction
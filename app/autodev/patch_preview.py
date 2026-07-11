from app.autodev.change_transaction import ChangeTransaction
from app.autodev.diff_builder import DiffBuilder


class PatchPreview:

    def __init__(self):
        self.diff_builder = DiffBuilder()

    def build(
        self,
        transaction: ChangeTransaction
    ) -> str:

        lines = [
            "AUTODEV PATCH PREVIEW",
            f"Cel: {transaction.goal}",
            f"Target: {transaction.target or 'brak'}",
            f"Status: {transaction.status}",
            f"Liczba plików: {len(transaction.changes)}",
            ""
        ]

        if not transaction.changes:
            lines.append(
                "Brak zmian w transakcji."
            )

            return "\n".join(lines)

        for index, change in enumerate(
            transaction.changes,
            start=1
        ):
            lines.append("=" * 70)
            lines.append(
                f"ZMIANA {index}"
            )
            lines.append(
                f"Plik: {change.path}"
            )
            lines.append(
                f"Status: {change.status}"
            )
            lines.append("")

            diff = self.diff_builder.build(
                old_content=change.old_content,
                new_content=change.new_content,
                path=change.path
            )

            lines.append(diff)
            lines.append("")

        lines.append("=" * 70)
        lines.append(
            "To jest wyłącznie podgląd. "
            "Żaden plik nie został zmieniony."
        )

        return "\n".join(lines)
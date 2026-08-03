from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from app.jarvis_experience.owner_access import OwnerAccessGate


def ensure_owner_pin(parent: QWidget, project_root: str | Path) -> bool:
    """Create the return PIN only while the owner window is active."""
    gate = OwnerAccessGate(project_root)
    if gate.has_pin():
        return True
    QMessageBox.information(
        parent,
        "Zabezpieczenie trybu właściciela",
        "Przed pierwszym wejściem do trybu klienta ustaw prywatny PIN. "
        "Będzie potrzebny tylko do powrotu do panelu właściciela.",
    )
    first, accepted = QInputDialog.getText(
        parent, "Ustaw PIN właściciela", "Nowy PIN (4–12 cyfr):",
        QLineEdit.Password,
    )
    if not accepted:
        return False
    second, accepted = QInputDialog.getText(
        parent, "Ustaw PIN właściciela", "Powtórz PIN:", QLineEdit.Password,
    )
    if not accepted:
        return False
    if first != second:
        QMessageBox.warning(parent, "Ustaw PIN", "Wpisane PIN-y są różne.")
        return False
    try:
        gate.set_pin(first)
    except ValueError as error:
        QMessageBox.warning(parent, "Ustaw PIN", str(error))
        return False
    QMessageBox.information(
        parent, "PIN ustawiony",
        "Tryb klienta jest gotowy. PIN zachowaj wyłącznie dla siebie.",
    )
    return True

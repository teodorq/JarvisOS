from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from app.jarvis_experience.owner_access import OwnerAccessGate


class ClientOwnerAccess:
    """Hidden, PIN-protected owner access used by the client shell."""

    def __init__(
        self,
        parent: QWidget,
        project_root: str | Path,
        on_unlocked: Callable[[], None],
    ) -> None:
        self.parent = parent
        self.gate = OwnerAccessGate(project_root)
        self.on_unlocked = on_unlocked

    def request_unlock(self) -> None:
        if not self.gate.has_pin():
            QMessageBox.warning(
                self.parent,
                "Dostęp właściciela",
                "PIN właściciela nie jest skonfigurowany. Uruchom ponownie "
                "JARVIS w trybie właściciela i ustaw PIN przed wejściem do "
                "trybu klienta.",
            )
            return
        pin, accepted = QInputDialog.getText(
            self.parent,
            "Dostęp właściciela",
            "Wpisz PIN właściciela:",
            QLineEdit.Password,
        )
        if not accepted:
            return
        allowed, message = self.gate.verify(pin)
        if allowed:
            self.on_unlocked()
            return
        QMessageBox.warning(self.parent, "Dostęp właściciela", message)

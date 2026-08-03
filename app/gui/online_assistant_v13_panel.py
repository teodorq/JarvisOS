from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill


class OnlineAssistantV13Panel(QWidget):
    """Compact owner panel for B131-B135 Online Assistant 1.3 Beta."""

    command_requested = Signal(str)

    def __init__(self, controller: Any) -> None:
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = SectionCard(
            "B131–B135 — ONLINE ASSISTANT 1.3 BETA",
            "Retry tylko dla odczytu, bezpieczny tryb offline, workflow Gmail, inteligencja kalendarza i wersjonowane dokumenty.",
        )
        top = QHBoxLayout()
        self.overall = StatusPill("OCZEKUJE NA AUDYT", "neutral")
        top.addWidget(self.overall)
        top.addStretch(1)
        header.content_layout.addLayout(top)
        layout.addWidget(header)

        self.rows = {
            "session": InfoRow("B131 sesja Google"),
            "offline": InfoRow("Tryb offline"),
            "gmail": InfoRow("B132 operacje Gmail"),
            "calendar": InfoRow("B133 analizy kalendarza"),
            "documents": InfoRow("B134 wersje dokumentów"),
            "audit": InfoRow("B135 audyt"),
            "gates": InfoRow("Bramki"),
            "beta": InfoRow("Online Assistant 1.3 Beta"),
            "sending": InfoRow("Automatyczna wysyłka"),
        }
        card = SectionCard(
            "STAN PAKIETU B131–B135",
            "Każdy zapis, archiwizacja, etykieta, wydarzenie i wysyłka nadal wymagają potwierdzenia TAK.",
        )
        for row in self.rows.values():
            card.content_layout.addWidget(row)
        card.content_layout.addLayout(self._actions(
            ("STATUS 1.3", "Pokaż status asystenta online 1.3"),
            ("TEST SESJI", "Sprawdź niezawodność Google Workspace"),
            ("GMAIL", "Pokaż skrzynkę pracy Gmail"),
            ("TYDZIEŃ", "Pokaż plan tygodnia Google"),
            ("TERMINY", "Zaproponuj terminy Google czas 30"),
            ("AUDYT B135", "Uruchom audyt B135"),
            ("POTWIERDŹ", "Potwierdź B135"),
        ))
        layout.addWidget(card)
        self.refresh()

    def _actions(self, *items: tuple[str, str]) -> QHBoxLayout:
        layout = QHBoxLayout()
        for title, command in items:
            button = QPushButton(title)
            button.setObjectName("SecondaryButton")
            button.clicked.connect(
                lambda _checked=False, value=command: self.command_requested.emit(value)
            )
            layout.addWidget(button)
        layout.addStretch(1)
        return layout

    def refresh(self) -> None:
        status = self.controller.status()
        reliability = dict(status.get("reliability", {}) or {})
        probe = dict(reliability.get("last_probe", {}) or {})
        gmail = dict(status.get("gmail", {}) or {})
        calendar = dict(status.get("calendar", {}) or {})
        drive = dict(status.get("drive", {}) or {})
        beta = dict(status.get("beta", {}) or {})
        ready = bool(beta.get("beta_ready"))
        self.overall.set_status(
            "ONLINE ASSISTANT 1.3 BETA" if ready else "OCZEKUJE NA AUDYT",
            "healthy" if ready else "neutral",
        )
        self.rows["session"].set_value(display_status(probe.get("status", "NOT_CHECKED")))
        self.rows["offline"].set_value("TAK" if reliability.get("offline_mode") else "NIE")
        self.rows["gmail"].set_value(gmail.get("operation_count", 0))
        self.rows["calendar"].set_value(calendar.get("analysis_count", 0))
        self.rows["documents"].set_value(drive.get("document_version_count", 0))
        self.rows["audit"].set_value(display_status(beta.get("latest_audit_status", "NOT_RUN")))
        self.rows["gates"].set_value(f"{beta.get('gates_passed', 0)}/{beta.get('gates_total', 12)}")
        self.rows["beta"].set_value("GOTOWA" if ready else "OCZEKUJE")
        self.rows["sending"].set_value("WYŁĄCZONA")

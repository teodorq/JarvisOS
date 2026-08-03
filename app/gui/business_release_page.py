from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.user_text import naturalize_user_text
from app.business.business_edition_service import BusinessEditionService
from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill


class BusinessReleasePage(QWidget):
    """B87-B88 deployment package and Release Candidate administration."""

    command_requested = Signal(str)

    def __init__(self, service: BusinessEditionService) -> None:
        super().__init__()
        self.service = service
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(self._build_toolbar())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 4, 0)
        content.setSpacing(10)
        content.addWidget(self._build_installation())
        content.addWidget(self._build_release())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)
        self.feedback = QLabel("Gotowy.")
        self.feedback.setObjectName("Muted")
        root.addWidget(self.feedback)
        self.refresh()

    def _build_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("WDROŻENIE I RELEASE CANDIDATE B87–B88")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Przenośny instalator, pierwsze uruchomienie, deinstalacja i bramki RC1."
        )
        subtitle.setObjectName("Muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        layout.addLayout(heading)
        layout.addStretch(1)
        self.overall = StatusPill("SPRAWDZANIE", "neutral")
        refresh = QPushButton("ODŚWIEŻ")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(self.overall)
        layout.addWidget(refresh)
        return toolbar

    def _build_installation(self) -> QWidget:
        card = SectionCard(
            "B87 — Instalator Business Edition",
            "Buduje czysty pakiet instalacyjny, inicjalizuje profil i eksportuje bezpieczny deinstalator.",
        )
        self.install_rows = {
            "status": InfoRow("Status"),
            "version": InfoRow("Wersja"),
            "first_run": InfoRow("Pierwsze uruchomienie"),
            "packages": InfoRow("Pakiety instalacyjne"),
            "latest": InfoRow("Ostatni pakiet"),
            "directory": InfoRow("Katalog eksportu"),
        }
        for row in self.install_rows.values():
            card.content_layout.addWidget(row)
        buttons = QHBoxLayout()
        buttons.addWidget(self._command_button(
            "INICJALIZUJ", "Inicjalizuj pierwsze uruchomienie Business Edition"
        ))
        buttons.addWidget(self._command_button(
            "EKSPORTUJ INSTALATOR", "Eksportuj instalator Business Edition"
        ))
        buttons.addWidget(self._command_button(
            "EKSPORTUJ DEINSTALATOR", "Eksportuj bezpieczny deinstalator", primary=False
        ))
        buttons.addWidget(self._command_button(
            "POKAŻ STATUS", "Pokaż status instalatora Business Edition", primary=False
        ))
        buttons.addStretch(1)
        card.content_layout.addLayout(buttons)
        return card

    def _build_release(self) -> QWidget:
        card = SectionCard(
            "B88 — JARVIS OS RC1",
            "Sprawdza licencję, integralność, checkpoint, testy, aktualizacje i politykę bezpieczeństwa.",
        )
        self.release_rows = {
            "status": InfoRow("Status"),
            "version": InfoRow("Wersja RC"),
            "validation": InfoRow("Macierz testów"),
            "gates": InfoRow("Bramki zaliczone"),
            "latest": InfoRow("Ostatni RC1"),
        }
        for row in self.release_rows.values():
            card.content_layout.addWidget(row)
        self.gate_rows = {
            "installation_ready": InfoRow("Instalator B87"),
            "license_active": InfoRow("Licencja"),
            "integrity_verified": InfoRow("Integralność SHA-256"),
            "checkpoint_verified": InfoRow("Checkpoint Disaster Recovery"),
            "test_matrix_passed": InfoRow("Pełny zestaw testów"),
            "audit_available": InfoRow("Centrum audytu"),
            "updates_clean": InfoRow("Pakiety aktualizacji"),
            "safety_locked": InfoRow("Polityka bezpieczeństwa"),
        }
        for row in self.gate_rows.values():
            card.content_layout.addWidget(row)
        buttons = QHBoxLayout()
        buttons.addWidget(self._command_button(
            "EKSPORTUJ RC1", "Eksportuj Release Candidate RC1"
        ))
        buttons.addWidget(self._command_button(
            "ZWERYFIKUJ RC1", "Zweryfikuj Release Candidate RC1", primary=False
        ))
        buttons.addWidget(self._command_button(
            "POKAŻ STATUS", "Pokaż status Release Candidate RC1", primary=False
        ))
        buttons.addStretch(1)
        card.content_layout.addLayout(buttons)
        return card

    def _command_button(
        self,
        label: str,
        command: str,
        *,
        primary: bool = True,
    ) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("PrimaryButton" if primary else "SecondaryButton")
        button.clicked.connect(
            lambda _checked=False, value=command: self.command_requested.emit(value)
        )
        return button

    def refresh(self) -> None:
        status = self.service.business_release_status()
        installation = dict(status.get("installation", {}) or {})
        first_run = dict(installation.get("first_run", {}) or {})
        self.install_rows["status"].set_value(display_status(installation.get("status")))
        self.install_rows["version"].set_value(installation.get("version", "—"))
        self.install_rows["first_run"].set_value(
            "GOTOWE" if first_run.get("completed") else "NIEZAINICJALIZOWANE"
        )
        self.install_rows["packages"].set_value(installation.get("package_count", 0))
        self.install_rows["latest"].set_value(
            installation.get("latest_setup_package") or "Brak"
        )
        self.install_rows["directory"].set_value(
            installation.get("export_directory", "—")
        )

        release = dict(status.get("release_candidate", {}) or {})
        validation = dict(release.get("validation", {}) or {})
        gates = dict(release.get("gates", {}) or {})
        passed = sum(1 for value in gates.values() if value)
        self.release_rows["status"].set_value(display_status(release.get("status")))
        self.release_rows["version"].set_value(release.get("version", "—"))
        self.release_rows["validation"].set_value(validation.get("status", "PENDING"))
        self.release_rows["gates"].set_value(f"{passed}/{len(gates)}")
        self.release_rows["latest"].set_value(release.get("latest_release") or "Brak")
        for name, row in self.gate_rows.items():
            row.set_value("OK" if gates.get(name) else "WYMAGA UWAGI")

        ready = bool(release.get("release_ready"))
        self.overall.set_status(
            "RC1 GOTOWY" if ready else "BRAMKI RC1",
            "healthy" if ready else "accent",
        )
        self.feedback.setText(naturalize_user_text(
            status.get("reason", "Gotowy.")
        ))

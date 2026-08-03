from __future__ import annotations

from typing import Any

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


class BusinessOperationsPage(QWidget):
    """B84-B86 audit, checkpoint and local update administration."""

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
        content.addWidget(self._build_audit())
        content.addWidget(self._build_recovery())
        content.addWidget(self._build_updates())
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
        title = QLabel("OPERACJE BIZNESOWE B84–B86")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Audyt, checkpointy Disaster Recovery i bezpieczne aktualizacje lokalne."
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

    def _build_audit(self) -> QWidget:
        card = SectionCard(
            "B84 — Centrum audytu",
            "Zbiera decyzje uprawnień i operacje Business Edition w ograniczonym dzienniku.",
        )
        self.audit_rows = {
            "status": InfoRow("Status"),
            "events": InfoRow("Zdarzenia"),
            "allowed": InfoRow("Zezwolenia"),
            "denied": InfoRow("Odmowy"),
            "exports": InfoRow("Eksporty"),
        }
        for row in self.audit_rows.values():
            card.content_layout.addWidget(row)
        buttons = QHBoxLayout()
        export = self._command_button(
            "EKSPORTUJ RAPORT AUDYTU", "Eksportuj raport audytu"
        )
        status = self._command_button(
            "POKAŻ STATUS", "Pokaż status centrum audytu", primary=False
        )
        buttons.addWidget(export)
        buttons.addWidget(status)
        buttons.addStretch(1)
        card.content_layout.addLayout(buttons)
        return card

    def _build_recovery(self) -> QWidget:
        card = SectionCard(
            "B85 — Backup i Disaster Recovery",
            "Tworzy checkpoint projektu, weryfikuje SHA-256 i przygotowuje restore offline.",
        )
        self.recovery_rows = {
            "status": InfoRow("Status"),
            "count": InfoRow("Checkpointy"),
            "latest": InfoRow("Ostatni checkpoint"),
            "verification": InfoRow("Weryfikacja"),
            "directory": InfoRow("Katalog"),
        }
        for row in self.recovery_rows.values():
            card.content_layout.addWidget(row)
        buttons = QHBoxLayout()
        buttons.addWidget(self._command_button("UTWÓRZ CHECKPOINT", "Utwórz checkpoint Business Edition"))
        buttons.addWidget(self._command_button("ZWERYFIKUJ", "Zweryfikuj ostatni checkpoint", primary=False))
        buttons.addWidget(self._command_button("PRZYGOTUJ RESTORE", "Przygotuj pakiet przywracania", primary=False))
        buttons.addStretch(1)
        card.content_layout.addLayout(buttons)
        return card

    def _build_updates(self) -> QWidget:
        card = SectionCard(
            "B86 — Centrum aktualizacji",
            "Skanuje lokalne ZIP-y, weryfikuje manifest, izoluje staging i eksportuje installer."
        )
        self.update_rows = {
            "status": InfoRow("Status"),
            "packages": InfoRow("Pakiety"),
            "valid": InfoRow("Poprawne"),
            "staged": InfoRow("Staged update"),
            "inbox": InfoRow("Katalog aktualizacji"),
        }
        for row in self.update_rows.values():
            card.content_layout.addWidget(row)
        buttons = QHBoxLayout()
        buttons.addWidget(self._command_button("SKANUJ", "Skanuj pakiety aktualizacji", primary=False))
        buttons.addWidget(self._command_button("PRZYGOTUJ STAGING", "Przygotuj aktualizację Business Edition"))
        buttons.addWidget(self._command_button("EKSPORTUJ INSTALLER", "Eksportuj instalator aktualizacji", primary=False))
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
        button.clicked.connect(lambda _checked=False, value=command: self.command_requested.emit(value))
        return button

    def refresh(self) -> None:
        status = self.service.business_operations_status()
        audit = dict(status.get("audit", {}) or {})
        counts = dict(audit.get("decision_counts", {}) or {})
        self.audit_rows["status"].set_value(display_status(audit.get("status")))
        self.audit_rows["events"].set_value(audit.get("event_count", 0))
        self.audit_rows["allowed"].set_value(counts.get("ALLOW", 0))
        self.audit_rows["denied"].set_value(counts.get("DENY", 0))
        self.audit_rows["exports"].set_value(len(audit.get("exports", [])))

        recovery = dict(status.get("disaster_recovery", {}) or {})
        latest = dict(recovery.get("latest_checkpoint", {}) or {})
        self.recovery_rows["status"].set_value(display_status(recovery.get("status")))
        self.recovery_rows["count"].set_value(recovery.get("checkpoint_count", 0))
        self.recovery_rows["latest"].set_value(latest.get("path", "Brak"))
        self.recovery_rows["verification"].set_value(latest.get("verification", "BRAK"))
        self.recovery_rows["directory"].set_value(recovery.get("checkpoint_directory", "—"))

        updates = dict(status.get("updates", {}) or {})
        staged = dict(updates.get("staged_update", {}) or {})
        self.update_rows["status"].set_value(display_status(updates.get("status")))
        self.update_rows["packages"].set_value(updates.get("package_count", 0))
        self.update_rows["valid"].set_value(updates.get("valid_package_count", 0))
        self.update_rows["staged"].set_value(staged.get("version", "Brak"))
        self.update_rows["inbox"].set_value(updates.get("inbox_directory", "—"))

        ready = bool(status.get("success"))
        self.overall.set_status(
            "OPERACJE GOTOWE" if ready else "WYMAGA UWAGI",
            "healthy" if ready else "danger",
        )
        self.feedback.setText(naturalize_user_text(
            status.get("reason", "Gotowy.")
        ))

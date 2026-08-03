from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.user_text import naturalize_user_text
from app.business.business_edition_service import BusinessEditionService
from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill


class BusinessPlatformPage(QWidget):
    """B81-B83 organization, license and access administration."""

    configuration_changed = Signal()
    data_changed = Signal()

    def __init__(self, service: BusinessEditionService) -> None:
        super().__init__()
        self.service = service
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("PLATFORMA BIZNESOWA B81–B83")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Profile organizacji, licencje lokalne i role operatorów."
        )
        subtitle.setObjectName("Muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        toolbar_layout.addLayout(heading)
        toolbar_layout.addStretch(1)
        self.overall = StatusPill("SPRAWDZANIE", "neutral")
        refresh = QPushButton("ODŚWIEŻ")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.refresh)
        toolbar_layout.addWidget(self.overall)
        toolbar_layout.addWidget(refresh)
        root.addWidget(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 4, 0)
        content.setSpacing(10)

        content.addWidget(self._build_profiles())
        content.addWidget(self._build_license())
        content.addWidget(self._build_access())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self.feedback = QLabel("Gotowy.")
        self.feedback.setObjectName("Muted")
        root.addWidget(self.feedback)
        self.refresh()

    def _build_profiles(self) -> QWidget:
        card = SectionCard(
            "B81 — Profile organizacji",
            "Twórz snapshoty konfiguracji, aktywuj je i eksportuj do JSON.",
        )
        self.profile_status = InfoRow("Status")
        self.profile_count = InfoRow("Liczba profili")
        card.content_layout.addWidget(self.profile_status)
        card.content_layout.addWidget(self.profile_count)
        row = QHBoxLayout()
        self.profile_selector = QComboBox()
        self.profile_selector.setMinimumWidth(320)
        snapshot = QPushButton("UTWÓRZ SNAPSHOT")
        snapshot.setObjectName("SecondaryButton")
        snapshot.clicked.connect(self._snapshot_profile)
        activate = QPushButton("AKTYWUJ")
        activate.setObjectName("PrimaryButton")
        activate.clicked.connect(self._activate_profile)
        export = QPushButton("EKSPORTUJ")
        export.setObjectName("SecondaryButton")
        export.clicked.connect(self._export_profile)
        row.addWidget(self.profile_selector, 1)
        row.addWidget(snapshot)
        row.addWidget(activate)
        row.addWidget(export)
        card.content_layout.addLayout(row)
        return card

    def _build_license(self) -> QWidget:
        card = SectionCard(
            "B82 — Licencja i aktywacja offline",
            "Tryb właścicielski, trial, odcisk komputera i pakiet aktywacyjny.",
        )
        self.license_rows = {
            "status": InfoRow("Status"),
            "mode": InfoRow("Tryb"),
            "fingerprint": InfoRow("Odcisk komputera"),
            "expiry": InfoRow("Ważna do"),
        }
        for row in self.license_rows.values():
            card.content_layout.addWidget(row)

        request_row = QHBoxLayout()
        trial = QPushButton("URUCHOM TRIAL 14 DNI")
        trial.setObjectName("SecondaryButton")
        trial.clicked.connect(self._start_trial)
        request = QPushButton("EKSPORTUJ WNIOSEK")
        request.setObjectName("SecondaryButton")
        request.clicked.connect(self._export_license_request)
        deactivate = QPushButton("DEZAKTYWUJ PLIK LICENCJI")
        deactivate.setObjectName("SecondaryButton")
        deactivate.clicked.connect(self._deactivate_license)
        request_row.addWidget(trial)
        request_row.addWidget(request)
        request_row.addWidget(deactivate)
        request_row.addStretch(1)
        card.content_layout.addLayout(request_row)

        self.activation_package = QTextEdit()
        self.activation_package.setPlaceholderText(
            "Wklej pakiet JSON aktywacji offline dla tego odcisku komputera."
        )
        self.activation_package.setLineWrapMode(QTextEdit.WidgetWidth)
        self.activation_package.setWordWrapMode(QTextOption.WrapAnywhere)
        self.activation_package.setMaximumHeight(110)
        card.content_layout.addWidget(self.activation_package)
        activate = QPushButton("AKTYWUJ PAKIET OFFLINE")
        activate.setObjectName("PrimaryButton")
        activate.clicked.connect(self._activate_offline)
        card.content_layout.addWidget(activate)
        return card

    def _build_access(self) -> QWidget:
        card = SectionCard(
            "B83 — Role i uprawnienia",
            "OWNER, ADMIN, OPERATOR, AUDITOR i VIEWER z lokalnym audytem decyzji.",
        )
        self.access_rows = {
            "principal": InfoRow("Użytkownik"),
            "role": InfoRow("Aktywna rola"),
            "permissions": InfoRow("Uprawnienia"),
            "events": InfoRow("Zdarzenia audytu"),
        }
        for row in self.access_rows.values():
            card.content_layout.addWidget(row)
        role_row = QHBoxLayout()
        self.role_selector = QComboBox()
        for role in ("OWNER", "ADMIN", "OPERATOR", "AUDITOR", "VIEWER"):
            self.role_selector.addItem(role, role)
        apply_role = QPushButton("ZASTOSUJ ROLĘ")
        apply_role.setObjectName("PrimaryButton")
        apply_role.clicked.connect(self._set_role)
        role_row.addWidget(self.role_selector, 1)
        role_row.addWidget(apply_role)
        card.content_layout.addLayout(role_row)
        return card

    def refresh(self) -> None:
        profiles = self.service.organization_profiles.status()
        active_id = str(profiles.get("active_profile_id", ""))
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        active_index = 0
        for index, profile in enumerate(profiles.get("profiles", [])):
            profile_id = str(profile.get("profile_id", ""))
            label = str(profile.get("name", "Profil"))
            self.profile_selector.addItem(label, profile_id)
            if profile_id == active_id:
                active_index = index
        if self.profile_selector.count():
            self.profile_selector.setCurrentIndex(active_index)
        self.profile_selector.blockSignals(False)
        self.profile_status.set_value(display_status(profiles.get("status")))
        self.profile_count.set_value(profiles.get("profile_count", 0))

        license_status = self.service.license_manager.status(
            self.service.config_store.ensure()
        )
        self.license_rows["status"].set_value(
            display_status(license_status.get("status"))
        )
        self.license_rows["mode"].set_value(
            display_status(license_status.get("mode"))
        )
        self.license_rows["fingerprint"].set_value(
            license_status.get("machine_fingerprint", "—")
        )
        self.license_rows["expiry"].set_value(
            license_status.get("expires_at") or "Bezterminowa"
        )

        access = self.service.access_control.status()
        self.access_rows["principal"].set_value(access.get("principal", "—"))
        self.access_rows["role"].set_value(access.get("active_role", "—"))
        permissions = list(access.get("permissions", []) or [])
        self.access_rows["permissions"].set_value(
            "PEŁNE" if "*" in permissions else ", ".join(permissions) or "BRAK"
        )
        self.access_rows["events"].set_value(len(access.get("audit_events", [])))
        role_index = self.role_selector.findData(access.get("active_role"))
        self.role_selector.setCurrentIndex(max(0, role_index))

        ready = bool(license_status.get("active")) and bool(profiles.get("success"))
        self.overall.set_status(
            "PLATFORMA GOTOWA" if ready else "WYMAGA UWAGI",
            "healthy" if ready else "danger",
        )
        self.data_changed.emit()

    def _snapshot_profile(self) -> None:
        result = self.service.organization_profiles.snapshot_current()
        self._show_result(result)
        self.refresh()

    def _activate_profile(self) -> None:
        profile_id = self.profile_selector.currentData()
        result = self.service.organization_profiles.activate(str(profile_id or ""))
        self._show_result(result)
        if result.get("success"):
            self.configuration_changed.emit()
        self.refresh()

    def _export_profile(self) -> None:
        result = self.service.organization_profiles.export_active()
        path = result.get("export_path", "")
        self._show_result(result, f"Wyeksportowano: {path}")
        self.refresh()

    def _start_trial(self) -> None:
        status = self.service.license_manager.start_trial(
            self.service.config_store.ensure()
        )
        self._show_result(
            {"success": status.get("active"), "status": status.get("status")},
            "Trial został zapisany lokalnie.",
        )
        self.refresh()

    def _export_license_request(self) -> None:
        result = self.service.license_manager.export_activation_request(
            self.service.config_store.ensure()
        )
        self._show_result(result, f"Wniosek: {result.get('export_path', '')}")
        self.refresh()

    def _deactivate_license(self) -> None:
        status = self.service.license_manager.deactivate(
            self.service.config_store.ensure()
        )
        self._show_result(
            {"success": status.get("active"), "status": status.get("status")},
            "Usunięto lokalny plik licencji; tryb właścicielski może pozostać aktywny.",
        )
        self.refresh()

    def _activate_offline(self) -> None:
        value = self.activation_package.toPlainText().strip()
        status = self.service.license_manager.activate_offline(
            value,
            self.service.config_store.ensure(),
        )
        self._show_result(
            {"success": status.get("active"), "status": status.get("status")},
            f"Status aktywacji: {status.get('status', 'UNKNOWN')}",
        )
        self.refresh()

    def _set_role(self) -> None:
        result = self.service.access_control.set_active_role(
            str(self.role_selector.currentData())
        )
        self._show_result(result)
        self.refresh()

    def _show_result(
        self,
        result: dict[str, Any],
        success_text: str | None = None,
    ) -> None:
        success = bool(result.get("success"))
        text = (
            success_text
            if success and success_text
            else str(result.get("reason") or result.get("status") or "Gotowe.")
        )
        errors = list(result.get("errors", []) or [])
        if errors:
            text = f"{text} | {errors[0]}"
        self.feedback.setText(naturalize_user_text(text))
        self.feedback.setObjectName("Healthy" if success else "Danger")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

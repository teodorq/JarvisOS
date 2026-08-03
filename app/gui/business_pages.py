from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
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
from app.gui.business_display import display_environment, display_status
from app.gui.business_widgets import (
    InfoRow,
    QuickCommandButton,
    SectionCard,
    StatusPill,
)


class ConsolePage(QWidget):
    """Główna konsola poleceń z bezpiecznymi skrótami."""

    command_submitted = Signal(str)
    quick_command_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("KONSOLA OPERACYJNA")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Bezpieczne dowodzenie, obserwacja i potwierdzanie działań")
        subtitle.setObjectName("Muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        toolbar_layout.addLayout(heading)
        toolbar_layout.addStretch(1)
        self.state_pill = StatusPill("GOTOWY NA POLECENIE", "healthy")
        self.license_pill = StatusPill("LICENCJA AKTYWNA", "accent")
        toolbar_layout.addWidget(self.state_pill)
        toolbar_layout.addWidget(self.license_pill)
        layout.addWidget(toolbar)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setAcceptRichText(False)
        self.chat.setObjectName("OperationsLog")
        self.chat.setLineWrapMode(QTextEdit.WidgetWidth)
        self.chat.setWordWrapMode(QTextOption.WrapAnywhere)
        self.chat.document().setMaximumBlockCount(2000)
        layout.addWidget(self.chat, 1)

        self.quick_panel = QFrame()
        self.quick_panel.setObjectName("QuickPanel")
        quick_layout = QGridLayout(self.quick_panel)
        quick_layout.setContentsMargins(12, 10, 12, 10)
        quick_layout.setHorizontalSpacing(8)
        quick_layout.setVerticalSpacing(8)
        shortcuts = (
            ("BUSINESS", "Pokaż status Business Edition", "status i licencja"),
            ("AUTONOMIA", "Pokaż centrum sterowania autonomią", "centrum B73"),
            ("INCYDENTY", "Pokaż status centrum incydentów", "monitoring B69"),
            ("ODZYSKIWANIE", "Pokaż status odzyskiwania autonomii", "plany B70"),
        )
        for index, (title, command, subtitle) in enumerate(shortcuts):
            button = QuickCommandButton(title, command, subtitle)
            button.clicked.connect(
                lambda _checked=False, value=command: self.quick_command_requested.emit(value)
            )
            quick_layout.addWidget(button, index // 2, index % 2)
        layout.addWidget(self.quick_panel)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Wpisz polecenie dla JARVIS OS…")
        self.entry.returnPressed.connect(self._submit)
        self.submit_button = QPushButton("WYKONAJ")
        self.submit_button.setObjectName("PrimaryButton")
        self.submit_button.setMinimumWidth(122)
        self.submit_button.clicked.connect(self._submit)
        input_row.addWidget(self.entry, 1)
        input_row.addWidget(self.submit_button)
        layout.addLayout(input_row)

    def _submit(self) -> None:
        text = self.entry.text().strip()
        if not text:
            return
        self.entry.clear()
        self.command_submitted.emit(text)

    def prepare_command(self, command: str) -> None:
        self.entry.setText(command)
        self.entry.setFocus()
        self.entry.selectAll()

    def append(self, text: str) -> None:
        message = naturalize_user_text(text)
        if not message:
            return
        self.chat.append(message)
        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_state(self, text: str, tone: str = "neutral") -> None:
        self.state_pill.set_status(naturalize_user_text(text), tone)

    def set_license(self, text: str, active: bool) -> None:
        self.license_pill.set_status(
            naturalize_user_text(text), "accent" if active else "danger"
        )

    def show_quick_actions(self, visible: bool) -> None:
        self.quick_panel.setVisible(bool(visible))


class SettingsPage(QWidget):
    """Lokalne ustawienia organizacji i wyglądu."""

    save_requested = Signal(dict)
    reset_requested = Signal()

    ACCENTS = (
        ("Błękit Jarvisa", "#4DA3FF"),
        ("Elektryczny cyjan", "#39D9FF"),
        ("Fiolet zarządczy", "#8D7CFF"),
        ("Zieleń bezpieczeństwa", "#55D98B"),
        ("Bursztyn sygnałowy", "#FFB454"),
    )
    ENVIRONMENTS = (
        ("Rozwój właścicielski", "OWNER DEVELOPMENT"),
        ("Środowisko testowe", "STAGING"),
        ("Produkcja", "PRODUCTION"),
        ("Demo", "DEMO"),
    )

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        heading = QFrame()
        heading.setObjectName("PageToolbar")
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel("ORGANIZACJA I WYGLĄD")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Konfiguracja jest lokalna i atomowa; nie może osłabić polityki bezpieczeństwa."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)
        root.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 4, 0)
        content.setSpacing(10)

        identity = SectionCard(
            "Tożsamość",
            "Nazwy widoczne w nagłówku, systemie Windows i raportach Business Edition.",
        )
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        self.product_name = QLineEdit()
        self.organization = QLineEdit()
        self.environment = QComboBox()
        for label, value in self.ENVIRONMENTS:
            self.environment.addItem(label, value)
        self.environment.setEditable(True)
        self.support_contact = QLineEdit()
        form.addRow("Nazwa produktu", self.product_name)
        form.addRow("Organizacja", self.organization)
        form.addRow("Środowisko", self.environment)
        form.addRow("Kontakt wsparcia", self.support_contact)
        identity.content_layout.addLayout(form)
        content.addWidget(identity)

        appearance = SectionCard(
            "Wygląd",
            "Wybierz kolor akcentu i widoczność bezpiecznych skrótów poleceń.",
        )
        appearance_form = QFormLayout()
        appearance_form.setHorizontalSpacing(18)
        self.accent = QComboBox()
        for label, value in self.ACCENTS:
            self.accent.addItem(label, value)
        self.quick_actions = QComboBox()
        self.quick_actions.addItem("Włączone", True)
        self.quick_actions.addItem("Wyłączone", False)
        appearance_form.addRow("Kolor akcentu", self.accent)
        appearance_form.addRow("Skróty poleceń", self.quick_actions)
        appearance.content_layout.addLayout(appearance_form)
        content.addWidget(appearance)

        safety = SectionCard(
            "Bezpieczeństwo wymuszone",
            "Ustawienia niezmienne: automatyczne zatwierdzanie wyłączone, potwierdzenia wymagane.",
        )
        safety_label = QLabel(
            "● AUTO-APPROVE: WYŁĄCZONE    ● POTWIERDZENIE: WYMAGANE    "
            "● AKTYWNE WYKONANIA: MAKS. 1    ● KOD ZDALNY: WYŁĄCZONY"
        )
        safety_label.setObjectName("Healthy")
        safety_label.setWordWrap(True)
        safety.content_layout.addWidget(safety_label)
        content.addWidget(safety)
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()
        self.feedback = QLabel("Zmiany nie zostały zapisane.")
        self.feedback.setObjectName("Muted")
        actions.addWidget(self.feedback)
        actions.addStretch(1)
        reset = QPushButton("PRZYWRÓĆ DOMYŚLNE")
        reset.setObjectName("SecondaryButton")
        reset.clicked.connect(self.reset_requested.emit)
        save = QPushButton("ZAPISZ KONFIGURACJĘ")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)
        actions.addWidget(reset)
        actions.addWidget(save)
        root.addLayout(actions)

    def load_config(self, config: dict[str, Any]) -> None:
        self.product_name.setText(str(config.get("product_name", "")))
        self.organization.setText(str(config.get("organization", "")))
        environment = str(config.get("environment", "OWNER DEVELOPMENT"))
        index = self.environment.findData(environment)
        if index < 0:
            self.environment.addItem(display_environment(environment), environment)
            index = self.environment.count() - 1
        self.environment.setCurrentIndex(index)
        self.support_contact.setText(str(config.get("support_contact", "")))
        accent = str(config.get("accent_color", "#4DA3FF")).upper()
        index = self.accent.findData(accent)
        if index < 0:
            self.accent.addItem(f"Własny {accent}", accent)
            index = self.accent.count() - 1
        self.accent.setCurrentIndex(index)
        visible = bool(dict(config.get("ui", {}) or {}).get("show_quick_actions", True))
        quick_index = self.quick_actions.findData(visible)
        self.quick_actions.setCurrentIndex(max(0, quick_index))
        self.feedback.setText("Konfiguracja wczytana.")

    def _save(self) -> None:
        environment = self.environment.currentData()
        if environment is None:
            environment = self.environment.currentText()
        self.save_requested.emit({
            "product_name": self.product_name.text(),
            "organization": self.organization.text(),
            "environment": environment,
            "support_contact": self.support_contact.text(),
            "accent_color": self.accent.currentData(),
            "ui": {"show_quick_actions": bool(self.quick_actions.currentData())},
        })

    def set_feedback(self, text: str, healthy: bool = True) -> None:
        self.feedback.setText(naturalize_user_text(text))
        self.feedback.setObjectName("Healthy" if healthy else "Danger")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)


class TrustPage(QWidget):
    """Podgląd licencji, integralności i wymuszonej polityki."""

    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("LICENCJA, ZAUFANIE I INTEGRALNOŚĆ")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Lokalna tożsamość instalacji i kontrola krytycznych plików.")
        subtitle.setObjectName("Muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        toolbar_layout.addLayout(heading)
        toolbar_layout.addStretch(1)
        self.overall = StatusPill("SPRAWDZANIE", "neutral")
        refresh = QPushButton("ODŚWIEŻ")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.refresh_requested.emit)
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

        license_card = SectionCard("Tożsamość licencji")
        self.license_rows = {
            "status": InfoRow("Status"),
            "mode": InfoRow("Tryb"),
            "license_id": InfoRow("ID licencji"),
            "organization": InfoRow("Organizacja"),
            "fingerprint": InfoRow("Odcisk komputera"),
            "expiry": InfoRow("Ważna do"),
        }
        for row in self.license_rows.values():
            license_card.content_layout.addWidget(row)
        content.addWidget(license_card)

        integrity_card = SectionCard(
            "Baseline integralności",
            "SHA-256 wykrywa zmianę lub brak plików; nie jest szyfrowaniem kodu.",
        )
        self.integrity_rows = {
            "status": InfoRow("Status"),
            "checked": InfoRow("Sprawdzone pliki"),
            "generated": InfoRow("Utworzono baseline"),
        }
        for row in self.integrity_rows.values():
            integrity_card.content_layout.addWidget(row)
        self.integrity_details = QTextEdit()
        self.integrity_details.setObjectName("IntegrityDetails")
        self.integrity_details.setReadOnly(True)
        self.integrity_details.setLineWrapMode(QTextEdit.WidgetWidth)
        self.integrity_details.setWordWrapMode(QTextOption.WrapAnywhere)
        self.integrity_details.setMaximumHeight(120)
        integrity_card.content_layout.addWidget(self.integrity_details)
        content.addWidget(integrity_card)

        policy = SectionCard("Wymuszona polityka biznesowa")
        self.safety_rows = {
            "approval": InfoRow("Automatyczne zatwierdzanie"),
            "confirmation": InfoRow("Potwierdzenia"),
            "executions": InfoRow("Aktywne wykonania"),
            "remote": InfoRow("Zdalne wykonywanie kodu"),
        }
        for row in self.safety_rows.values():
            policy.content_layout.addWidget(row)
        content.addWidget(policy)
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def load_status(self, status: dict[str, Any]) -> None:
        license_status = dict(status.get("license", {}) or {})
        integrity = dict(status.get("integrity", {}) or {})
        safety = dict(status.get("safety", {}) or {})
        active = bool(license_status.get("active"))
        integrity_ok = integrity.get("status") in {"VERIFIED", "BASELINE_PENDING"}
        self.overall.set_status(
            "ZAUFANIE POTWIERDZONE" if active and integrity_ok else "WYMAGA UWAGI",
            "healthy" if active and integrity_ok else "danger",
        )
        values = {
            "status": display_status(license_status.get("status")),
            "mode": display_status(license_status.get("mode")),
            "license_id": license_status.get("license_id", "—"),
            "organization": license_status.get("organization", "—"),
            "fingerprint": license_status.get("machine_fingerprint", "—"),
            "expiry": license_status.get("expires_at") or "Bezterminowa",
        }
        for key, value in values.items():
            self.license_rows[key].set_value(value)
        self.integrity_rows["status"].set_value(display_status(integrity.get("status")))
        self.integrity_rows["checked"].set_value(integrity.get("files_checked", 0))
        self.integrity_rows["generated"].set_value(integrity.get("generated_at") or "—")
        changed = list(integrity.get("changed", []) or [])
        missing = list(integrity.get("missing", []) or [])
        details = []
        if changed:
            details.append("ZMIENIONE:\n- " + "\n- ".join(map(str, changed)))
        if missing:
            details.append("BRAKUJĄCE:\n- " + "\n- ".join(map(str, missing)))
        self.integrity_details.setPlainText("\n\n".join(details) or "Brak wykrytych zmian.")
        self.safety_rows["approval"].set_value(
            "WŁĄCZONE" if safety.get("auto_approve") else "WYŁĄCZONE"
        )
        self.safety_rows["confirmation"].set_value(
            "WYMAGANE" if safety.get("require_confirmation") else "WYŁĄCZONE"
        )
        self.safety_rows["executions"].set_value(
            f"MAKS. {safety.get('max_active_executions', 1)}"
        )
        self.safety_rows["remote"].set_value(
            "WŁĄCZONE" if safety.get("allow_remote_code_execution") else "WYŁĄCZONE"
        )

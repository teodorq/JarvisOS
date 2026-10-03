from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui.client_settings_extensions import install_client_settings_controls


def build_client_setup_page(window: Any) -> QWidget:
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setObjectName("ClientSetupScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    viewport = QWidget()
    viewport.setObjectName("ClientSetupViewport")
    viewport_layout = QVBoxLayout(viewport)
    viewport_layout.addStretch(1)

    card = QFrame()
    card.setObjectName("SetupCard")
    card.setMaximumWidth(720)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    content = QVBoxLayout(card)
    content.setContentsMargins(34, 30, 34, 30)
    content.setSpacing(16)
    _add_profile_controls(window, content)
    install_client_settings_controls(window, content)

    safety = QLabel(
        "● Ważne działania zawsze wymagają Twojej zgody\n"
        "● Twoje dane pozostają pod kontrolą użytkownika"
    )
    safety.setObjectName("ClientHealthy")
    safety.setWordWrap(True)
    content.addWidget(safety)
    start = QPushButton("ZAPISZ I URUCHOM JARVISA")
    start.setObjectName("ClientPrimary")
    start.clicked.connect(window._save_setup)
    content.addWidget(start)
    window.setup_feedback = QLabel("")
    window.setup_feedback.setObjectName("ClientWarning")
    content.addWidget(window.setup_feedback)

    centered = QHBoxLayout()
    centered.addStretch(1)
    centered.addWidget(card, 1)
    centered.addStretch(1)
    viewport_layout.addLayout(centered)
    viewport_layout.addStretch(1)
    scroll.setWidget(viewport)
    outer.addWidget(scroll)
    return page


def _add_profile_controls(window: Any, content: QVBoxLayout) -> None:
    title = QLabel("PIERWSZE URUCHOMIENIE")
    title.setObjectName("ClientState")
    subtitle = QLabel(
        "Ustaw podstawy. Wszystko pozostaje lokalnie na tym komputerze."
    )
    subtitle.setObjectName("ClientMessage")
    subtitle.setWordWrap(True)
    content.addWidget(title)
    content.addWidget(subtitle)
    content.addSpacing(8)
    name_label = QLabel("Jak mam się do Ciebie zwracać?")
    name_label.setObjectName("ClientHint")
    window.name_entry = QLineEdit()
    window.name_entry.setPlaceholderText("Twoje imię")
    content.addWidget(name_label)
    content.addWidget(window.name_entry)
    voice_label = QLabel("Obsługa głosowa")
    voice_label.setObjectName("ClientHint")
    window.voice_combo = QComboBox()
    window.voice_combo.addItem("Włączona", True)
    window.voice_combo.addItem("Wyłączona", False)
    content.addWidget(voice_label)
    content.addWidget(window.voice_combo)
    mode_label = QLabel("Sposób rozmowy")
    mode_label.setObjectName("ClientHint")
    window.interaction_combo = QComboBox()
    window.interaction_combo.addItem("Głos i tekst", "VOICE_AND_TEXT")
    window.interaction_combo.addItem("Tylko tekst", "TEXT_ONLY")
    content.addWidget(mode_label)
    content.addWidget(window.interaction_combo)


__all__ = ["build_client_setup_page"]

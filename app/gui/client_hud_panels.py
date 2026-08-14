from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.gui.client_exit_intent import request_jarvis_shutdown


def build_client_hud_row(window: Any, halo: Any) -> QHBoxLayout:
    """Build a Stark-like HUD with controls kept away from the central core."""
    row = QHBoxLayout()
    row.setSpacing(26)
    row.addWidget(_left_column(window), 0, Qt.AlignVCenter)
    row.addStretch(1)
    row.addWidget(halo, 0, Qt.AlignCenter)
    row.addStretch(1)
    row.addWidget(_chat_dock(window), 0, Qt.AlignVCenter)
    return row


def _left_column(window: Any) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudCornerColumn")
    frame.setMinimumWidth(210)
    frame.setMaximumWidth(238)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(18)
    layout.addWidget(_status_panel(window))
    layout.addStretch(1)
    layout.addWidget(_menu_panel(window, show_tools=True))
    return frame


def _status_panel(window: Any) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudCornerPanel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(15, 14, 15, 15)
    layout.setSpacing(7)

    title = QLabel("STATUS SYSTEMU")
    title.setObjectName("HudCornerTitle")
    layout.addWidget(title)

    voice_online = bool(getattr(getattr(window, "owner_window", None), "voice_online", False))
    voice = "GŁOS  •  GOTOWY" if voice_online else "GŁOS  •  TRYB TEKSTOWY"
    for text in (
        "● RDZEŃ  •  ONLINE",
        f"● {voice}",
        "● AZURE  •  POŁĄCZONE",
        "● OCHRONA  •  AKTYWNA",
    ):
        indicator = QLabel(text)
        indicator.setObjectName("HudStatusLine")
        layout.addWidget(indicator)
    return frame


def _menu_panel(window: Any, *, show_tools: bool = False) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudCornerPanel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(15, 14, 15, 15)
    layout.setSpacing(6)

    title = QLabel("MENU")
    title.setObjectName("HudCornerTitle")
    layout.addWidget(title)

    if show_tools:
        tools = _menu_button("NARZĘDZIA")
        tools.clicked.connect(lambda: getattr(window, "experience_v2").toggle_tools())
        window.tools_button = tools
        layout.addWidget(tools)

    settings = _menu_button("USTAWIENIA")
    settings.clicked.connect(lambda: _open_owner_settings(window))
    window.settings_button = settings
    layout.addWidget(settings)

    leave = _menu_button("WYJDŹ")
    leave.clicked.connect(lambda: request_jarvis_shutdown(window))
    window.exit_button = leave
    layout.addWidget(leave)
    hint = QLabel("Powiedz: „Pokaż mój plan na dziś”")
    hint.setObjectName("HudCornerHint")
    hint.setWordWrap(True)
    layout.addWidget(hint)
    guide = QLabel("Kliknij albo poproś własnymi słowami")
    guide.setObjectName("HudCornerHint")
    guide.setWordWrap(True)
    layout.addWidget(guide)
    return frame


def _menu_button(label: str) -> QPushButton:
    button = QPushButton(label)
    button.setObjectName("HudMenuAction")
    button.setCursor(Qt.PointingHandCursor)
    return button


def _open_owner_settings(window: Any) -> None:
    """Keep the protected owner gate before revealing system settings."""
    access = getattr(window, "owner_access", None)
    if access is None:
        return
    was_visible = window.isVisible()
    access.request_unlock()
    owner = getattr(window, "owner_window", None)
    show_page = getattr(owner, "_show_page", None)
    if was_visible and not window.isVisible() and callable(show_page):
        show_page("settings")


def _chat_dock(window: Any) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudChatDock")
    frame.setMinimumWidth(270)
    frame.setMaximumWidth(330)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 16, 14, 16)
    layout.setSpacing(8)
    layout.addStretch(1)

    title = QLabel("ROZMOWA")
    title.setObjectName("HudCornerTitle")
    layout.addWidget(title)
    placeholder = QLabel("Czat pojawi się tutaj po wydaniu polecenia.")
    placeholder.setObjectName("HudChatPlaceholder")
    placeholder.setWordWrap(True)
    layout.addWidget(placeholder)

    host = QVBoxLayout()
    host.setContentsMargins(0, 0, 0, 0)
    host.setSpacing(0)
    layout.addLayout(host)
    layout.addStretch(1)

    window.conversation_host_layout = host
    window.conversation_placeholder = placeholder
    window.conversation_dock = frame
    return frame


__all__ = ["build_client_hud_row"]

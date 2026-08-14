from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.gui.client_exit_intent import request_jarvis_shutdown


def build_client_hud_row(window: Any, halo: Any) -> QHBoxLayout:
    """Build a sparse, edge-mounted cinematic HUD around the entity."""
    row = QHBoxLayout()
    row.setSpacing(18)
    row.addWidget(_left_column(window), 0, Qt.AlignVCenter)
    row.addStretch(1)
    row.addWidget(halo, 0, Qt.AlignCenter)
    row.addStretch(1)
    row.addWidget(_right_column(window), 0, Qt.AlignVCenter)
    return row


def _left_column(window: Any) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudEdgeColumn")
    frame.setMinimumWidth(178)
    frame.setMaximumWidth(212)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(_status_card("RDZEŃ", "ONLINE"))
    layout.addWidget(_status_card("GŁOS", _voice_status(window)))
    layout.addWidget(_status_card("AZURE", "POŁĄCZONE"))
    layout.addStretch(1)
    layout.addWidget(_menu_panel(window, show_tools=True))
    return frame


def _voice_status(window: Any) -> str:
    online = bool(getattr(getattr(window, "owner_window", None), "voice_online", False))
    return "GOTOWY" if online else "TRYB TEKSTOWY"


def _status_card(label: str, value: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudStatusCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 9, 12, 9)
    layout.setSpacing(2)
    key = QLabel(label)
    key.setObjectName("HudStatusKey")
    status = QLabel(f"● {value}")
    status.setObjectName("HudStatusValue")
    layout.addWidget(key)
    layout.addWidget(status)
    return frame


def _menu_panel(window: Any, *, show_tools: bool = False) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudMenuPanel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 11, 12, 11)
    layout.setSpacing(4)
    title = QLabel("MENU")
    title.setObjectName("HudPanelTitle")
    layout.addWidget(title)
    if show_tools:
        tools = _menu_button("NARZĘDZIA")
        tools.clicked.connect(lambda: getattr(window, "experience_v2").toggle_tools())
        window.tools_button = tools
        layout.addWidget(tools)
    settings = _menu_button("USTAWIENIA")
    settings.clicked.connect(lambda: _open_client_settings(window))
    window.settings_button = settings
    layout.addWidget(settings)
    leave = _menu_button("WYJDŹ")
    leave.clicked.connect(lambda: request_jarvis_shutdown(window))
    window.exit_button = leave
    layout.addWidget(leave)
    hint = QLabel("Pokaż mój plan na dziś")
    hint.setObjectName("HudMicroHint")
    hint.setWordWrap(True)
    layout.addWidget(hint)
    guide = QLabel("Kliknij albo poproś własnymi słowami")
    guide.setObjectName("HudMicroHint")
    guide.setWordWrap(True)
    layout.addWidget(guide)
    return frame


def _menu_button(label: str) -> QPushButton:
    button = QPushButton(label)
    button.setObjectName("HudMenuAction")
    button.setCursor(Qt.PointingHandCursor)
    return button


def _open_client_settings(window: Any) -> None:
    setup_page = getattr(window, "setup_page", None)
    stack = getattr(window, "stack", None)
    if setup_page is None or stack is None:
        return
    tools = getattr(getattr(window, "experience_v2", None), "tools", None)
    hide_tools = getattr(tools, "hide_tools", None)
    if callable(hide_tools):
        hide_tools()
    title = next(
        (label for label in setup_page.findChildren(QLabel)
         if label.objectName() == "ClientState"),
        None,
    )
    subtitle = next(
        (label for label in setup_page.findChildren(QLabel)
         if label.objectName() == "ClientMessage"),
        None,
    )
    start = next(
        (button for button in setup_page.findChildren(QPushButton)
         if button.objectName() == "ClientPrimary"),
        None,
    )
    if title is not None:
        title.setText("USTAWIENIA JARVIS OS")
    if subtitle is not None:
        subtitle.setText("Zmień imię, obsługę głosową lub sposób rozmowy.")
    if start is not None:
        start.setText("ZAPISZ USTAWIENIA")
        if getattr(window, "client_settings_back", None) is None:
            back = _menu_button("WRÓĆ")
            back.setObjectName("ClientSecondary")
            back.clicked.connect(
                lambda: stack.setCurrentWidget(window.client_page)
            )
            start.parentWidget().layout().insertWidget(
                start.parentWidget().layout().indexOf(start) + 1,
                back,
            )
            window.client_settings_back = back
    feedback = getattr(window, "setup_feedback", None)
    if feedback is not None:
        feedback.clear()
    stack.setCurrentWidget(setup_page)
    name_entry = getattr(window, "name_entry", None)
    if name_entry is not None:
        name_entry.setFocus(Qt.OtherFocusReason)


def _right_column(window: Any) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudEdgeColumn")
    frame.setMinimumWidth(230)
    frame.setMaximumWidth(276)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch(1)
    layout.addWidget(_chat_dock(window))
    return frame


def _chat_dock(window: Any) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudChatDock")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(7)
    title = QLabel("ROZMOWA")
    title.setObjectName("HudPanelTitle")
    layout.addWidget(title)
    status_host = QVBoxLayout()
    status_host.setContentsMargins(0, 0, 0, 0)
    status_host.setSpacing(4)
    layout.addLayout(status_host)
    placeholder = QLabel("Czat otworzy się po wydaniu polecenia.")
    placeholder.setObjectName("HudChatPlaceholder")
    placeholder.setWordWrap(True)
    layout.addWidget(placeholder)
    conversation_host = QVBoxLayout()
    conversation_host.setContentsMargins(0, 0, 0, 0)
    layout.addLayout(conversation_host)
    command_box = QFrame()
    command_box.setObjectName("HudCommandBox")
    command_layout = QHBoxLayout(command_box)
    command_layout.setContentsMargins(5, 5, 5, 5)
    command_layout.setSpacing(5)
    layout.addWidget(command_box)
    window.conversation_host_layout = conversation_host
    window.conversation_placeholder = placeholder
    window.status_host_layout = status_host
    window.command_input_layout = command_layout
    window.command_box = command_box
    window.conversation_dock = frame
    return frame


def mount_client_status(window: Any) -> None:
    """Keep the center clean by mounting live task state inside the chat."""
    widgets = (
        window.state_label,
        window.message_label,
        window.activity_label,
        window.activity_progress,
        window.confirm_frame,
    )
    for widget in widgets:
        widget.setParent(window.conversation_dock)
        window.status_host_layout.addWidget(widget)
    window.state_label.setAlignment(Qt.AlignLeft)
    window.message_label.setAlignment(Qt.AlignLeft)
    window.message_label.setMinimumHeight(0)
    window.message_label.setMaximumHeight(64)
    window.activity_label.setAlignment(Qt.AlignLeft)


def mount_client_command_input(window: Any) -> None:
    """Move the existing tested input controls into the compact chat dock."""
    send = next(
        button for button in window.findChildren(QPushButton)
        if button.objectName() == "ClientPrimary"
        and button.parentWidget() is window.command_entry.parentWidget()
    )
    controls = (window.command_entry, window.listen_button, send)
    for widget in controls:
        widget.setParent(window.command_box)
        window.command_input_layout.addWidget(widget, 1 if widget is window.command_entry else 0)
    window.listen_button.setText("MÓW")
    send.setText("›")
    send.setObjectName("HudSendAction")


__all__ = ["build_client_hud_row", "mount_client_command_input", "mount_client_status"]

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.gui.client_exit_intent import request_jarvis_shutdown


def build_client_hud_row(window: Any, halo: Any) -> QHBoxLayout:
    """Build the tested client controls around the central JARVIS core."""
    row = QHBoxLayout()
    row.setSpacing(24)
    row.addStretch(1)
    row.addWidget(
        _rail(
            window,
            "DZISIAJ",
            "● CODZIENNA PRACA",
            (
                ("PLAN DNIA", "Pokaż mój plan na dziś"),
                ("POCZTA", "Znajdź najważniejszą wiadomość"),
                ("DOKUMENTY", "Znajdź ostatnio używany dokument"),
            ),
        ),
        0,
        Qt.AlignVCenter,
    )
    row.addWidget(halo, 0, Qt.AlignCenter)
    row.addWidget(
        _rail(
            window,
            "ORGANIZACJA",
            "● BEZPIECZNE ODCZYTY",
            (
                ("KALENDARZ", "Co mam dziś w kalendarzu?"),
                ("PRZYPOMNIENIA", "Pokaż najbliższe przypomnienia"),
            ),
            show_tools=True,
        ),
        0,
        Qt.AlignVCenter,
    )
    row.addStretch(1)
    return row


def _rail(
    window: Any,
    title: str,
    status: str,
    commands: tuple[tuple[str, str], ...],
    *,
    show_tools: bool = False,
) -> QFrame:
    frame = QFrame()
    frame.setObjectName("HudRail")
    frame.setMinimumWidth(192)
    frame.setMaximumWidth(248)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 15, 14, 15)
    layout.setSpacing(8)

    heading = QLabel(title)
    heading.setObjectName("HudRailTitle")
    layout.addWidget(heading)
    indicator = QLabel(status)
    indicator.setObjectName("HudRailStatus")
    layout.addWidget(indicator)
    layout.addSpacing(5)

    for label, command in commands:
        button = QPushButton(label)
        button.setObjectName("HudAction")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(
            lambda _checked=False, value=command: window._submit_text(value)
        )
        layout.addWidget(button)

    if show_tools:
        tools = QPushButton("WIĘCEJ")
        tools.setObjectName("HudAction")
        tools.setCursor(Qt.PointingHandCursor)
        tools.clicked.connect(lambda: getattr(window, "experience_v2").toggle_tools())
        window.tools_button = tools
        layout.addWidget(tools)
        leave = QPushButton("WYJDŹ")
        leave.setObjectName("HudAction")
        leave.setCursor(Qt.PointingHandCursor)
        leave.clicked.connect(lambda: request_jarvis_shutdown(window))
        window.exit_button = leave
        layout.addWidget(leave)

    layout.addStretch(1)
    hint = QLabel("Kliknij albo poproś własnymi słowami")
    hint.setObjectName("HudRailHint")
    hint.setWordWrap(True)
    layout.addWidget(hint)
    return frame

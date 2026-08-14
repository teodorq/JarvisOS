from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.core.user_text import naturalize_user_text


@dataclass(frozen=True)
class ClientToolAction:
    label: str
    command: str
    guided: bool = False
    hint: str = ""


SAFE_CLIENT_ACTIONS: tuple[tuple[str, tuple[ClientToolAction, ...]], ...] = (
    (
        "MÓJ DZIEŃ",
        (
            ClientToolAction("PODSUMOWANIE DNIA", "Jak minął dzień?"),
            ClientToolAction("NAJWAŻNIEJSZE TERAZ", "Co jest teraz najważniejsze?"),
            ClientToolAction("PLAN NA JUTRO", "Zaplanuj mój jutrzejszy dzień"),
            ClientToolAction("OSTATNIE DZIAŁANIA", "Co ostatnio udało mi się zrobić?"),
            ClientToolAction("RACHUNKI", "Podlicz moje rachunki do zapłaty"),
        ),
    ),
    (
        "POCZTA",
        (
            ClientToolAction("NAJNOWSZE", "Znajdź moje najnowsze wiadomości Gmail"),
            ClientToolAction("WAŻNE", "Znajdź ważne wiadomości Gmail"),
            ClientToolAction("NIEPRZECZYTANE", "Znajdź nieprzeczytane wiadomości Gmail"),
        ),
    ),
    (
        "KALENDARZ",
        (
            ClientToolAction("DZISIAJ", "Co mam dziś w kalendarzu?"),
            ClientToolAction("TEN TYDZIEŃ", "Pokaż mój kalendarz na ten tydzień"),
            ClientToolAction(
                "NOWE WYDARZENIE", "Dodaj do kalendarza ", True,
                "Dopisz nazwę, dzień i godzinę wydarzenia.",
            ),
        ),
    ),
    (
        "PLIKI I PAMIĘĆ",
        (
            ClientToolAction("OSTATNI DOKUMENT", "Znajdź ostatnio używany dokument"),
            ClientToolAction(
                "SZUKAJ DOKUMENTU", "Znajdź dokument ", True,
                "Dopisz nazwę lub słowa z dokumentu.",
            ),
            ClientToolAction(
                "NOWE PRZYPOMNIENIE", "Przypomnij mi ", True,
                "Dopisz, co i kiedy mam Ci przypomnieć.",
            ),
        ),
    ),
)


class ClientToolDrawer(QFrame):
    """Compact access to tested daily tools available in the client product."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.setObjectName("ClientToolsPanel")
        self._build()
        self.hide()
        parent_layout = window.message_label.parentWidget().layout()
        index = parent_layout.indexOf(window.activity_label)
        parent_layout.insertWidget(max(0, index), self)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 11, 15, 13)
        outer.setSpacing(9)
        header = QHBoxLayout()
        title = QLabel("CODZIENNE NARZĘDZIA")
        title.setObjectName("ClientToolsTitle")
        hint = QLabel("Funkcje dostępne w wersji klienta")
        hint.setObjectName("ClientToolsHint")
        close = QPushButton("ZAMKNIJ")
        close.setObjectName("ConversationClear")
        close.clicked.connect(self.hide_tools)
        header.addWidget(title)
        header.addWidget(hint)
        header.addStretch(1)
        header.addWidget(close)
        outer.addLayout(header)

        columns = QHBoxLayout()
        columns.setSpacing(13)
        self.action_buttons: list[QPushButton] = []
        for group, actions in SAFE_CLIENT_ACTIONS:
            column = QVBoxLayout()
            label = QLabel(group)
            label.setObjectName("ClientToolsGroup")
            column.addWidget(label)
            for action in actions:
                button = QPushButton(action.label)
                button.setObjectName("ClientToolAction")
                button.setCursor(Qt.PointingHandCursor)
                button.clicked.connect(
                    lambda _checked=False, selected=action: self.run(selected)
                )
                self.action_buttons.append(button)
                column.addWidget(button)
            column.addStretch(1)
            columns.addLayout(column, 1)
        outer.addLayout(columns)

    def toggle(self) -> None:
        self.setVisible(not self.isVisible())
        self._sync_button()

    def hide_tools(self) -> None:
        self.hide()
        self._sync_button()

    def run(self, action: ClientToolAction) -> None:
        self.hide_tools()
        if action.guided:
            self.window.command_entry.setText(action.command)
            self.window.command_entry.setCursorPosition(len(action.command))
            self.window.command_entry.setPlaceholderText(naturalize_user_text(action.hint))
            self.window.message_label.setText(naturalize_user_text(action.hint))
            self.window.activity_label.setText("Uzupełnij polecenie i naciśnij Enter.")
            self.window.command_entry.setFocus(Qt.OtherFocusReason)
            return
        self.window._submit_text(action.command)

    def _sync_button(self) -> None:
        button = getattr(self.window, "tools_button", None)
        if button is not None:
            if button.objectName() == "HudMenuAction":
                button.setText("ZAMKNIJ MENU" if self.isVisible() else "NARZĘDZIA")
                return
            button.setText("MNIEJ" if self.isVisible() else "WIĘCEJ")

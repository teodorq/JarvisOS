from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.core.user_text import naturalize_user_text
from app.gui.client_context_suggestions import context_suggestions


@dataclass(frozen=True)
class ClientToolAction:
    label: str
    command: str
    guided: bool = False
    hint: str = ""


SAFE_CLIENT_ACTIONS: tuple[tuple[str, tuple[ClientToolAction, ...]], ...] = (
    (
        "JARVIS",
        (
            ClientToolAction("STATUS JARVIS", "Status asystenta"),
            ClientToolAction("STAN KOMPUTERA", "Jaki jest stan komputera?"),
            ClientToolAction("STATUS GŁOSU", "Status głosu"),
            ClientToolAction("POGODA", "Jaka jest pogoda?"),
        ),
    ),
    (
        "MÓJ DZIEŃ",
        (
            ClientToolAction("PODSUMOWANIE DNIA", "Jak minął dzień?"),
            ClientToolAction("NAJWAŻNIEJSZE TERAZ", "Co jest teraz najważniejsze?"),
            ClientToolAction("PLAN NA JUTRO", "Zaplanuj mój jutrzejszy dzień"),
            ClientToolAction("OSTATNIE DZIAŁANIA", "Co ostatnio udało mi się zrobić?"),
            ClientToolAction("RACHUNKI", "Podlicz moje rachunki do zapłaty"),
            ClientToolAction("CO POTRAFIĘ", "Co potrafisz?"),
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
            ClientToolAction("INTEGRACJE", "Pokaż status integracji"),
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

        self.suggestion_title = QLabel("JARVIS PROPONUJE")
        self.suggestion_title.setObjectName("ClientSuggestionTitle")
        outer.addWidget(self.suggestion_title)
        suggestions = QHBoxLayout()
        suggestions.setSpacing(8)
        self.suggestion_buttons: list[QPushButton] = []
        for index in range(3):
            button = QPushButton()
            button.setObjectName("ClientSuggestionAction")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, selected=index: self._run_suggestion(
                    selected
                )
            )
            self.suggestion_buttons.append(button)
            suggestions.addWidget(button, 1)
        outer.addLayout(suggestions)
        self._current_suggestions = ()
        self._refresh_suggestions()

        self.search = QLineEdit()
        self.search.setObjectName("ClientToolSearch")
        self.search.setPlaceholderText("Szukaj funkcji, np. pogoda lub kalendarz…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_actions)
        outer.addWidget(self.search)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.action_buttons: list[QPushButton] = []
        self._indexed_actions: list[
            tuple[str, ClientToolAction, QPushButton]
        ] = []
        index = 0
        for group, actions in SAFE_CLIENT_ACTIONS:
            for action in actions:
                button = QPushButton(action.label)
                button.setObjectName("ClientToolAction")
                button.setCursor(Qt.PointingHandCursor)
                button.setToolTip(f"{group} • {action.command}")
                button.clicked.connect(
                    lambda _checked=False, selected=action: self.run(selected)
                )
                self.action_buttons.append(button)
                self._indexed_actions.append((group, action, button))
                grid.addWidget(button, index // 4, index % 4)
                index += 1
        for column in range(4):
            grid.setColumnStretch(column, 1)
        outer.addLayout(grid)

    def toggle(self) -> None:
        if not self.isVisible():
            self._refresh_suggestions()
        self.setVisible(not self.isVisible())
        self._sync_button()

    def hide_tools(self) -> None:
        self.hide()
        self.search.clear()
        self._sync_button()

    def _filter_actions(self, text: str) -> None:
        query = _search_key(text)
        for group, action, button in self._indexed_actions:
            haystack = _search_key(f"{group} {action.label} {action.command}")
            button.setVisible(not query or query in haystack)

    def _refresh_suggestions(self) -> None:
        period, suggestions = context_suggestions()
        self._current_suggestions = suggestions
        self.suggestion_title.setText(f"JARVIS PROPONUJE • {period}")
        for button, suggestion in zip(self.suggestion_buttons, suggestions):
            button.setText(suggestion.label)
            button.setToolTip(suggestion.command)

    def _run_suggestion(self, index: int) -> None:
        if index < 0 or index >= len(self._current_suggestions):
            return
        command = self._current_suggestions[index].command
        self.hide_tools()
        self.window._submit_text(command)

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


def _search_key(value: object) -> str:
    return str(value or "").casefold().translate(str.maketrans({
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    }))

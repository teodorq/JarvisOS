from __future__ import annotations

from collections import deque
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.gui.client_exit_intent import request_jarvis_shutdown
from app.gui.client_result_formatter import ClientResultCard, ClientResultFormatter
from app.gui.client_tool_drawer import ClientToolDrawer


class ClientExperienceV2:
    """Compact conversation timeline and visual polish for the client shell."""

    TERMINAL_STATES = {"success", "warning", "error", "important", "brief"}

    def __init__(self, window: Any) -> None:
        self.window = window
        self._messages: deque[tuple[str, str, ClientResultCard | None]] = deque(
            maxlen=8
        )
        self._last_assistant = ""
        self._install_panel()
        self.tools = ClientToolDrawer(window)
        self._wrap_runtime()
        self._polish_layout()

    def toggle_tools(self) -> None:
        self.tools.toggle()

    def add_user(self, text: object) -> None:
        value = " ".join(str(text or "").split())
        if value and value.casefold() not in {"tak", "nie"}:
            self._append("Ty", value, None)

    def add_assistant(
        self,
        event: dict[str, Any],
        card: ClientResultCard | None = None,
    ) -> None:
        state = str(event.get("state", "idle")).lower()
        confirmation = bool(event.get("requires_confirmation", False))
        if state not in self.TERMINAL_STATES and not confirmation:
            return
        presentation = card or ClientResultFormatter.format(
            event.get("message", ""),
            state=state,
            result_type=event.get("result_type", ""),
        )
        signature = f"{presentation.title}\n{presentation.body}"
        if not presentation.body or signature == self._last_assistant:
            return
        self._last_assistant = signature
        self._append("JARVIS", presentation.body, presentation)

    def _install_panel(self) -> None:
        frame = QFrame()
        frame.setObjectName("ConversationPanel")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(7)
        header = QHBoxLayout()
        title = QLabel("OSTATNIA ROZMOWA")
        title.setObjectName("ConversationTitle")
        clear = QPushButton("WYCZYŚĆ")
        clear.setObjectName("ConversationClear")
        clear.clicked.connect(self.clear)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(clear)
        outer.addLayout(header)
        scroll = QScrollArea()
        scroll.setObjectName("ConversationScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("ConversationBody")
        self._list = QVBoxLayout(body)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(6)
        self._list.addStretch(1)
        scroll.setWidget(body)
        scroll.setMinimumHeight(92)
        scroll.setMaximumHeight(190)
        outer.addWidget(scroll)
        self._scroll = scroll
        frame.hide()
        host = getattr(self.window, "conversation_host_layout", None)
        if host is not None:
            host.addWidget(frame)
        else:
            parent_layout = self.window.message_label.parentWidget().layout()
            index = parent_layout.indexOf(self.window.message_label)
            parent_layout.insertWidget(index + 1, frame)
        self.frame = frame

    def _wrap_runtime(self) -> None:
        original_submit: Callable[[str], None] = self.window._submit_text
        original_event: Callable[[object], None] = self.window._on_client_event

        def submit(text: str) -> None:
            self.tools.hide_tools()
            if request_jarvis_shutdown(self.window, text):
                return
            self.add_user(text)
            original_submit(text)

        def event(raw_event: object) -> None:
            payload = raw_event if isinstance(raw_event, dict) else {}
            clean = dict(payload)
            card = ClientResultFormatter.format(
                clean.get("message", ""),
                state=clean.get("state", "idle"),
                result_type=clean.get("result_type", ""),
            )
            display = dict(clean)
            display["message"] = card.summary
            original_event(display)
            self.add_assistant(clean, card)

        self.window._submit_text = submit
        self.window._on_client_event = event

    def _polish_layout(self) -> None:
        self.window.halo.setMinimumSize(400, 400)
        self.window.halo.setMaximumSize(860, 860)
        self.window.message_label.setMinimumHeight(42)
        self.window.message_label.setMaximumHeight(96)
        self.window.command_entry.setClearButtonEnabled(True)
        for button in getattr(self.window, "quick_buttons", []):
            button.hide()
        self.window.command_entry.setFocus(Qt.OtherFocusReason)

    def clear(self) -> None:
        self._messages.clear()
        self._last_assistant = ""
        self.frame.hide()
        placeholder = getattr(self.window, "conversation_placeholder", None)
        if placeholder is not None:
            placeholder.show()
        self._render()

    def _append(
        self,
        author: str,
        text: str,
        card: ClientResultCard | None,
    ) -> None:
        self._messages.append((author, text, card))
        placeholder = getattr(self.window, "conversation_placeholder", None)
        if placeholder is not None:
            placeholder.hide()
        self.frame.show()
        self._render()

    def _render(self) -> None:
        while self._list.count() > 1:
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for author, text, card in self._messages:
            if card is None:
                bubble = QLabel(f"{author}: {text}")
                bubble.setObjectName("ConversationUser")
                bubble.setWordWrap(True)
                bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self._list.insertWidget(self._list.count() - 1, bubble)
                continue
            result = QFrame()
            result.setObjectName("ConversationResultCard")
            layout = QVBoxLayout(result)
            layout.setContentsMargins(10, 7, 10, 8)
            layout.setSpacing(4)
            title = QLabel(card.title)
            title.setObjectName("ConversationResultTitle")
            body = QLabel(text)
            body.setObjectName("ConversationJarvis")
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(title)
            layout.addWidget(body)
            self._list.insertWidget(self._list.count() - 1, result)
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

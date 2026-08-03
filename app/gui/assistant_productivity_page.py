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

from app.assistant.controller import PersonalAssistantController
from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill


class AssistantProductivityPage(QWidget):
    """B96-B100 natural assistant, memory, voice and daily-work panel."""

    command_requested = Signal(str)

    def __init__(self, controller: PersonalAssistantController) -> None:
        super().__init__()
        self.controller = controller
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("ASYSTENT I CODZIENNA PRACA B96–B100")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Naturalna rozmowa, niezawodny pulpit, pamięć projektów, Głos 2.0 i workflow."
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
        content.addWidget(self._build_conversation())
        content.addWidget(self._build_desktop())
        content.addWidget(self._build_memory())
        content.addWidget(self._build_voice())
        content.addWidget(self._build_daily_work())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self.feedback = QLabel(
            "Operacje zapisu są przygotowywane jako polecenia i nadal wymagają potwierdzenia."
        )
        self.feedback.setObjectName("Muted")
        root.addWidget(self.feedback)
        self.refresh()

    def _build_conversation(self) -> QWidget:
        card = SectionCard(
            "B96 — Naturalna rozmowa",
            "Rozwiązuje grzecznościowe formy, wake word, krótkie follow-upy i kontekst do 50 tur.",
        )
        self.conversation_rows = {
            "status": InfoRow("Status"),
            "turns": InfoRow("Tury kontekstu"),
            "intent": InfoRow("Ostatnia intencja"),
            "target": InfoRow("Ostatni cel"),
        }
        for row in self.conversation_rows.values():
            card.content_layout.addWidget(row)
        row = QHBoxLayout()
        row.addWidget(self._command_button("POKAŻ STATUS", "Pokaż status rozmowy"))
        row.addWidget(self._command_button("WYCZYŚĆ KONTEKST", "Wyczyść kontekst rozmowy"))
        row.addStretch(1)
        card.content_layout.addLayout(row)
        return card

    def _build_desktop(self) -> QWidget:
        card = SectionCard(
            "B97 — Niezawodne sterowanie pulpitem",
            "Ograniczone próby, obserwacja wyniku i brak powtarzania nieodwracalnych akcji.",
        )
        self.desktop_rows = {
            "status": InfoRow("Status"),
            "executions": InfoRow("Operacje"),
            "verified": InfoRow("Potwierdzone"),
            "unverified": InfoRow("Bez twardego sygnału"),
            "failures": InfoRow("Błędy"),
        }
        for row in self.desktop_rows.values():
            card.content_layout.addWidget(row)
        card.content_layout.addWidget(
            self._command_button("STATUS PULPITU", "Pokaż status sterowania pulpitem")
        )
        return card

    def _build_memory(self) -> QWidget:
        card = SectionCard(
            "B98 — Pamięć projektów i przerwanej pracy",
            "Trwałe profile projektów, preferencje, sesje i możliwość powrotu do zadania.",
        )
        self.memory_rows = {
            "status": InfoRow("Status"),
            "projects": InfoRow("Projekty"),
            "active": InfoRow("Aktywny projekt"),
            "preferences": InfoRow("Preferencje"),
            "interrupted": InfoRow("Przerwane zadania"),
        }
        for row in self.memory_rows.values():
            card.content_layout.addWidget(row)
        row = QHBoxLayout()
        row.addWidget(self._command_button("STATUS PAMIĘCI", "Pokaż status pamięci projektów"))
        row.addWidget(
            self._command_button(
                "DODAJ JARVIS OS",
                f"Zapamiętaj projekt JARVIS OS w {self.controller.project_root}",
            )
        )
        row.addStretch(1)
        card.content_layout.addLayout(row)
        return card

    def _build_voice(self) -> QWidget:
        card = SectionCard(
            "B99 — Głos 2.0",
            "Polski pl-PL, polecenie w tej samej wypowiedzi co wake word i przerwanie syntezy.",
        )
        self.voice_rows = {
            "status": InfoRow("Status"),
            "language": InfoRow("Język"),
            "wake": InfoRow("Wake words"),
            "continuous": InfoRow("Tryb ciągły"),
            "interrupt": InfoRow("Przerwanie mowy"),
        }
        for row in self.voice_rows.values():
            card.content_layout.addWidget(row)
        row = QHBoxLayout()
        row.addWidget(self._command_button("STATUS GŁOSU", "Pokaż status głosu 2.0"))
        row.addWidget(self._command_button("WŁĄCZ CIĄGŁY", "Włącz tryb ciągły głosu"))
        row.addWidget(self._command_button("WYŁĄCZ CIĄGŁY", "Wyłącz tryb ciągły głosu"))
        row.addStretch(1)
        card.content_layout.addLayout(row)
        return card

    def _build_daily_work(self) -> QWidget:
        card = SectionCard(
            "B100 — Centrum codziennej pracy",
            "Wieloetapowe zadania, postęp, przypomnienia i lokalny raport do AI_PLIKI.",
        )
        self.daily_rows = {
            "status": InfoRow("Status"),
            "workflows": InfoRow("Zadania"),
            "active": InfoRow("Aktywne"),
            "progress": InfoRow("Postęp"),
            "next": InfoRow("Następny krok"),
            "reminders": InfoRow("Przypomnienia"),
        }
        for row in self.daily_rows.values():
            card.content_layout.addWidget(row)
        first = QHBoxLayout()
        first.addWidget(self._command_button("STATUS PRACY", "Pokaż centrum codziennej pracy"))
        first.addWidget(
            self._command_button(
                "UTWÓRZ DEMO",
                "Utwórz zadanie wieloetapowe Start dnia: Pokaż status systemu; Pokaż zadania; Zapisz raport",
            )
        )
        first.addWidget(self._command_button("URUCHOM", "Uruchom zadanie Start dnia"))
        first.addWidget(self._command_button("NASTĘPNY KROK", "Wykonano krok"))
        card.content_layout.addLayout(first)
        second = QHBoxLayout()
        second.addWidget(
            self._command_button("DODAJ PRZYPOMNIENIE", "Przypomnij mi o raporcie za 5 minut")
        )
        second.addWidget(
            self._command_button("EKSPORTUJ RAPORT", "Eksportuj raport codziennej pracy")
        )
        second.addStretch(1)
        card.content_layout.addLayout(second)
        return card

    def _command_button(self, title: str, command: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("SecondaryButton")
        button.clicked.connect(lambda _checked=False, value=command: self.command_requested.emit(value))
        return button

    def refresh(self) -> None:
        status = self.controller.status()
        self.overall.set_status("ASYSTENT GOTOWY", "healthy")

        conversation = dict(status.get("conversation", {}) or {})
        self.conversation_rows["status"].set_value(display_status(conversation.get("status")))
        self.conversation_rows["turns"].set_value(
            f"{conversation.get('turn_count', 0)}/{conversation.get('context_limit', 50)}"
        )
        self.conversation_rows["intent"].set_value(conversation.get("last_intent") or "BRAK")
        self.conversation_rows["target"].set_value(conversation.get("last_target") or "BRAK")

        desktop = dict(status.get("desktop", {}) or {})
        self.desktop_rows["status"].set_value(display_status(desktop.get("status")))
        self.desktop_rows["executions"].set_value(desktop.get("executions", 0))
        self.desktop_rows["verified"].set_value(desktop.get("success_count", 0))
        self.desktop_rows["unverified"].set_value(desktop.get("unverified_count", 0))
        self.desktop_rows["failures"].set_value(desktop.get("failure_count", 0))

        memory = dict(status.get("memory", {}) or {})
        active = dict(memory.get("active_project", {}) or {})
        self.memory_rows["status"].set_value(display_status(memory.get("status")))
        self.memory_rows["projects"].set_value(memory.get("project_count", 0))
        self.memory_rows["active"].set_value(active.get("name") or "BRAK")
        self.memory_rows["preferences"].set_value(memory.get("preference_count", 0))
        self.memory_rows["interrupted"].set_value(memory.get("interrupted_count", 0))

        voice = dict(status.get("voice", {}) or {})
        self.voice_rows["status"].set_value(display_status(voice.get("status")))
        self.voice_rows["language"].set_value(voice.get("language", "pl-PL"))
        self.voice_rows["wake"].set_value(", ".join(voice.get("wake_words", [])))
        self.voice_rows["continuous"].set_value("TAK" if voice.get("continuous_mode") else "NIE")
        self.voice_rows["interrupt"].set_value("TAK" if voice.get("interrupt_enabled") else "NIE")

        daily = dict(status.get("daily_work", {}) or {})
        active_workflow = dict(daily.get("active_workflow", {}) or {})
        self.daily_rows["status"].set_value(display_status(daily.get("status")))
        self.daily_rows["workflows"].set_value(daily.get("workflow_count", 0))
        self.daily_rows["active"].set_value(active_workflow.get("title") or "BRAK")
        self.daily_rows["progress"].set_value(
            f"{active_workflow.get('completed_steps', 0)}/{active_workflow.get('total_steps', 0)}"
        )
        self.daily_rows["next"].set_value(active_workflow.get("next_step") or "BRAK")
        self.daily_rows["reminders"].set_value(
            f"{daily.get('pending_reminders', 0)} / pilne {daily.get('due_reminders', 0)}"
        )

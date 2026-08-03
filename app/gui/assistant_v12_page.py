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

from app.assistant_v12.controller import AssistantV12Controller
from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill


class AssistantV12Page(QWidget):
    """Owner diagnostics and test panel for B121-B125."""

    command_requested = Signal(str)

    def __init__(self, controller: AssistantV12Controller) -> None:
        super().__init__()
        self.controller = controller
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(self._toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 4, 0)
        content.setSpacing(10)
        content.addWidget(self._conversation_card())
        content.addWidget(self._context_card())
        content.addWidget(self._router_card())
        content.addWidget(self._progress_card())
        content.addWidget(self._beta_card())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self.feedback = QLabel(
            "Wysyłka, synchronizacja i publikacja pozostają wyłączone; zapisy wymagają potwierdzenia."
        )
        self.feedback.setObjectName("Muted")
        root.addWidget(self.feedback)
        self.refresh()

    def _toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("ASYSTENT CODZIENNY 1.2 B121–B125")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Naturalna rozmowa, wspólny kontekst, router produktywności, postęp i Business 1.2 Beta."
        )
        subtitle.setObjectName("Muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        layout.addLayout(heading)
        layout.addStretch(1)
        self.overall = StatusPill("SPRAWDZANIE", "neutral")
        refresh = QPushButton("ODŚWIEŻ")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(self.overall)
        layout.addWidget(refresh)
        return toolbar

    def _conversation_card(self) -> QWidget:
        card = SectionCard(
            "B121 — Naturalna rozmowa 3.0",
            "Naturalne polskie polecenia, brakujące dane i krótkie doprecyzowania.",
        )
        self.conversation_rows = {
            "status": InfoRow("Status"),
            "example": InfoRow("Przykład"),
        }
        self._add_rows(card, self.conversation_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status asystenta 1.2"),
            ("MÓJ DZIEŃ", "Pokaż mój dzień"),
            ("TEST DOPYTANIA", "Dodaj spotkanie"),
        ))
        return card

    def _context_card(self) -> QWidget:
        card = SectionCard(
            "B122 — Wspólny kontekst",
            "Łączy tekst, głos, ostatnią intencję, temat i brakujące informacje.",
        )
        self.context_rows = {
            "status": InfoRow("Status"),
            "turns": InfoRow("Tury"),
            "topic": InfoRow("Aktywny temat"),
            "intent": InfoRow("Ostatnia intencja"),
            "pending": InfoRow("Oczekuje na"),
        }
        self._add_rows(card, self.context_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż kontekst 1.2"),
            ("WYCZYŚĆ", "Wyczyść kontekst 1.2"),
        ))
        return card

    def _router_card(self) -> QWidget:
        card = SectionCard(
            "B123 — Router produktywności",
            "Jedna bezpieczna ścieżka dla poczty, kalendarza, dokumentów, przypomnień i raportów.",
        )
        self.router_rows = {
            "status": InfoRow("Status"),
            "mail": InfoRow("Poczta"),
            "calendar": InfoRow("Kalendarz"),
            "documents": InfoRow("Dokumenty"),
            "reminders": InfoRow("Przypomnienia"),
            "remote": InfoRow("Zdalna synchronizacja"),
        }
        self._add_rows(card, self.router_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS POCZTY", "Pokaż status poczty"),
            ("KALENDARZ", "Pokaż status kalendarza"),
            ("DOKUMENT", "Znajdź dokument JARVIS"),
            ("PRZYPOMNIENIA", "Pokaż status przypomnień"),
        ))
        return card

    def _progress_card(self) -> QWidget:
        card = SectionCard(
            "B124 — Rzeczywisty postęp",
            "Fazy rozumienia, kontekstu, routingu, wykonania, weryfikacji i ograniczonego retry.",
        )
        self.progress_rows = {
            "status": InfoRow("Status"),
            "operations": InfoRow("Operacje"),
            "completed": InfoRow("Ukończone"),
            "failed": InfoRow("Błędy"),
            "retries": InfoRow("Retry"),
            "latest": InfoRow("Ostatnia faza"),
        }
        self._add_rows(card, self.progress_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS POSTĘPU", "Pokaż postęp asystenta"),
            ("RAPORT DNIA", "Generuj raport dnia"),
        ))
        return card

    def _beta_card(self) -> QWidget:
        card = SectionCard(
            "B125 — Business 1.2 Beta",
            "Osiem bramek gotowości; potwierdzenie nie publikuje programu automatycznie.",
        )
        self.beta_rows = {
            "status": InfoRow("Status"),
            "audits": InfoRow("Audyty"),
            "latest": InfoRow("Ostatni audyt"),
            "gates": InfoRow("Bramki"),
            "ready": InfoRow("Business 1.2 Beta"),
        }
        self._add_rows(card, self.beta_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status Business 1.2 Beta"),
            ("AUDYT 1.2", "Uruchom audyt Business 1.2"),
            ("POTWIERDŹ 1.2", "Potwierdź Business 1.2"),
        ))
        return card

    @staticmethod
    def _add_rows(card: SectionCard, rows: dict[str, InfoRow]) -> None:
        for row in rows.values():
            card.content_layout.addWidget(row)

    def _actions(self, *buttons: tuple[str, str]) -> QHBoxLayout:
        layout = QHBoxLayout()
        for title, command in buttons:
            button = QPushButton(title)
            button.setObjectName("SecondaryButton")
            button.clicked.connect(
                lambda _checked=False, value=command: self.command_requested.emit(value)
            )
            layout.addWidget(button)
        layout.addStretch(1)
        return layout

    def refresh(self) -> None:
        status = self.controller.status()
        self.overall.set_status(
            "BUSINESS 1.2 BETA" if status["beta"]["beta_ready"] else "ASYSTENT 1.2 GOTOWY",
            "healthy",
        )
        conversation = dict(status.get("conversation", {}) or {})
        context = dict(status.get("context", {}) or {})
        router = dict(status.get("router", {}) or {})
        progress = dict(status.get("progress", {}) or {})
        beta = dict(status.get("beta", {}) or {})
        latest = dict(progress.get("latest", {}) or {})

        self.conversation_rows["status"].set_value(display_status(conversation.get("status")))
        self.conversation_rows["example"].set_value("„Przypomnij mi jutro o 9 sprawdzić raport”")
        self.context_rows["status"].set_value(display_status(context.get("status")))
        self.context_rows["turns"].set_value(f"{context.get('turn_count', 0)}/{context.get('context_limit', 80)}")
        self.context_rows["topic"].set_value(context.get("active_topic") or "BRAK")
        self.context_rows["intent"].set_value(context.get("last_intent") or "BRAK")
        self.context_rows["pending"].set_value(context.get("pending_intent") or "BRAK")

        self.router_rows["status"].set_value(display_status(router.get("status")))
        self.router_rows["mail"].set_value("GOTOWA" if router.get("mail_ready") else "BŁĄD")
        self.router_rows["calendar"].set_value("GOTOWY" if router.get("calendar_ready") else "BŁĄD")
        self.router_rows["documents"].set_value("GOTOWE" if router.get("documents_ready") else "BŁĄD")
        self.router_rows["reminders"].set_value("GOTOWE" if router.get("reminders_ready") else "BŁĄD")
        self.router_rows["remote"].set_value("WYŁĄCZONA" if not router.get("remote_sync") else "WŁĄCZONA")

        self.progress_rows["status"].set_value(display_status(progress.get("status")))
        self.progress_rows["operations"].set_value(progress.get("operation_count", 0))
        self.progress_rows["completed"].set_value(progress.get("completed_count", 0))
        self.progress_rows["failed"].set_value(progress.get("failed_count", 0))
        self.progress_rows["retries"].set_value(progress.get("retry_count", 0))
        self.progress_rows["latest"].set_value(latest.get("phase") or "BRAK")

        self.beta_rows["status"].set_value(display_status(beta.get("status")))
        self.beta_rows["audits"].set_value(beta.get("audit_count", 0))
        self.beta_rows["latest"].set_value(beta.get("latest_audit_status", "NOT_RUN"))
        self.beta_rows["gates"].set_value(f"{beta.get('gates_passed', 0)}/{beta.get('gates_total', 8)}")
        self.beta_rows["ready"].set_value("GOTOWA" if beta.get("beta_ready") else "OCZEKUJE")

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

from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill
from app.intelligence.controller import IntelligenceSuiteController


class IntelligenceCenterPage(QWidget):
    """B101-B105 owner page for intelligence and controlled autonomy."""

    command_requested = Signal(str)

    def __init__(self, controller: IntelligenceSuiteController) -> None:
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
        content.addWidget(self._vision_card())
        content.addWidget(self._brain_card())
        content.addWidget(self._desktop_card())
        content.addWidget(self._memory_card())
        content.addWidget(self._autonomy_card())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self.feedback = QLabel(
            "Operacje zapisu i sterowania nadal przechodzą przez potwierdzenie TAK."
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
        title = QLabel("CENTRUM INTELIGENCJI B101–B105")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Vision 3.0, Brain 2.0, Desktop Agent 2.0, Memory 2.0 i kontrolowana autonomia."
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

    def _vision_card(self) -> QWidget:
        card = SectionCard(
            "B101 — Vision 3.0",
            "Stabilne identyfikatory elementów, zmiany ekranu i weryfikacja rezultatu akcji.",
        )
        self.vision_rows = {
            "status": InfoRow("Status"),
            "observations": InfoRow("Obserwacje"),
            "window": InfoRow("Ostatnie okno"),
            "elements": InfoRow("Elementy"),
            "verified": InfoRow("Zweryfikowane akcje"),
        }
        for row in self.vision_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("POKAŻ STATUS", "Pokaż status Vision 3.0"))
        actions.addWidget(self._button("ZAPISZ DEMO", "Zapisz obserwację Vision 3.0 demo"))
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _brain_card(self) -> QWidget:
        card = SectionCard(
            "B102 — Brain 2.0",
            "Jawna intencja, ryzyko, doprecyzowanie oraz plan ograniczony do bezpiecznych kroków.",
        )
        self.brain_rows = {
            "status": InfoRow("Status"),
            "plans": InfoRow("Plany"),
            "intent": InfoRow("Ostatnia intencja"),
            "risk": InfoRow("Ryzyko"),
            "steps": InfoRow("Kroki"),
        }
        for row in self.brain_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("STATUS BRAIN 2", "Pokaż status Brain 2.0"))
        actions.addWidget(
            self._button(
                "PLAN DEMO",
                "Przeanalizuj polecenie 2.0: Otwórz notatnik i sprawdź rezultat",
            )
        )
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _desktop_card(self) -> QWidget:
        card = SectionCard(
            "B103 — Desktop Agent 2.0",
            "Transakcje pulpitu, blokada szybkich duplikatów i zapis wyniku każdej akcji.",
        )
        self.desktop_rows = {
            "status": InfoRow("Status"),
            "transactions": InfoRow("Transakcje"),
            "verified": InfoRow("Potwierdzone"),
            "blocked": InfoRow("Zablokowane duplikaty"),
            "failures": InfoRow("Błędy"),
        }
        for row in self.desktop_rows.values():
            card.content_layout.addWidget(row)
        card.content_layout.addWidget(
            self._button("STATUS DESKTOP 2", "Pokaż status Desktop Agent 2.0")
        )
        return card

    def _memory_card(self) -> QWidget:
        card = SectionCard(
            "B104 — Memory 2.0",
            "Lokalny indeks wspomnień z deduplikacją, kategoriami i rankingiem trafień.",
        )
        self.memory_rows = {
            "status": InfoRow("Status"),
            "entries": InfoRow("Wpisy"),
            "categories": InfoRow("Kategorie"),
            "query": InfoRow("Ostatnie wyszukiwanie"),
            "results": InfoRow("Trafienia"),
        }
        for row in self.memory_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("STATUS PAMIĘCI 2", "Pokaż status pamięci 2.0"))
        actions.addWidget(
            self._button(
                "ZAPISZ DEMO",
                "Zapamiętaj w pamięci 2.0: Projekt JARVIS OS używa krótkich odpowiedzi i pełnych plików.",
            )
        )
        actions.addWidget(
            self._button("ZNAJDŹ DEMO", "Znajdź w pamięci 2.0: pełne pliki")
        )
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _autonomy_card(self) -> QWidget:
        card = SectionCard(
            "B105 — Centrum autonomii 2.0",
            "Jedno aktywne wykonanie, trwała kolejka, postęp, pauza, wznowienie i anulowanie.",
        )
        self.autonomy_rows = {
            "status": InfoRow("Status"),
            "jobs": InfoRow("Zadania"),
            "queue": InfoRow("Kolejka"),
            "active": InfoRow("Aktywne"),
            "progress": InfoRow("Postęp"),
            "next": InfoRow("Następny krok"),
        }
        for row in self.autonomy_rows.values():
            card.content_layout.addWidget(row)
        first = QHBoxLayout()
        first.addWidget(self._button("STATUS", "Pokaż status autonomii 2.0"))
        first.addWidget(
            self._button(
                "UTWÓRZ DEMO",
                "Utwórz zadanie autonomii 2.0: Test B105 | Sprawdź status; Zapisz raport; Zakończ",
            )
        )
        first.addWidget(self._button("URUCHOM", "Uruchom zadanie autonomii 2.0"))
        first.addWidget(self._button("NASTĘPNY ETAP", "Następny etap autonomii 2.0"))
        card.content_layout.addLayout(first)
        second = QHBoxLayout()
        second.addWidget(self._button("WSTRZYMAJ", "Wstrzymaj autonomię 2.0"))
        second.addWidget(self._button("WZNÓW", "Wznów autonomię 2.0"))
        second.addWidget(self._button("ANULUJ", "Anuluj autonomię 2.0"))
        second.addStretch(1)
        card.content_layout.addLayout(second)
        return card

    def _button(self, title: str, command: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("SecondaryButton")
        button.clicked.connect(
            lambda _checked=False, value=command: self.command_requested.emit(value)
        )
        return button

    def refresh(self) -> None:
        status = self.controller.status()
        self.overall.set_status("INTELIGENCJA GOTOWA", "healthy")
        self._refresh_vision(dict(status.get("vision", {}) or {}))
        self._refresh_brain(dict(status.get("brain", {}) or {}))
        self._refresh_desktop(dict(status.get("desktop", {}) or {}))
        self._refresh_memory(dict(status.get("memory", {}) or {}))
        self._refresh_autonomy(dict(status.get("autonomy", {}) or {}))

    def _refresh_vision(self, value: dict[str, Any]) -> None:
        self.vision_rows["status"].set_value(display_status(value.get("status")))
        self.vision_rows["observations"].set_value(value.get("observation_count", 0))
        self.vision_rows["window"].set_value(value.get("window_title") or "BRAK")
        self.vision_rows["elements"].set_value(value.get("element_count", 0))
        self.vision_rows["verified"].set_value(value.get("verified_actions", 0))

    def _refresh_brain(self, value: dict[str, Any]) -> None:
        self.brain_rows["status"].set_value(display_status(value.get("status")))
        self.brain_rows["plans"].set_value(value.get("turn_count", 0))
        self.brain_rows["intent"].set_value(value.get("last_intent") or "BRAK")
        self.brain_rows["risk"].set_value(value.get("last_risk") or "BRAK")
        self.brain_rows["steps"].set_value(value.get("last_steps", 0))

    def _refresh_desktop(self, value: dict[str, Any]) -> None:
        self.desktop_rows["status"].set_value(display_status(value.get("status")))
        self.desktop_rows["transactions"].set_value(value.get("transaction_count", 0))
        self.desktop_rows["verified"].set_value(value.get("verified_count", 0))
        self.desktop_rows["blocked"].set_value(value.get("duplicate_blocks", 0))
        self.desktop_rows["failures"].set_value(value.get("failure_count", 0))

    def _refresh_memory(self, value: dict[str, Any]) -> None:
        self.memory_rows["status"].set_value(display_status(value.get("status")))
        self.memory_rows["entries"].set_value(value.get("entry_count", 0))
        self.memory_rows["categories"].set_value(value.get("category_count", 0))
        self.memory_rows["query"].set_value(value.get("last_query") or "BRAK")
        self.memory_rows["results"].set_value(value.get("last_result_count", 0))

    def _refresh_autonomy(self, value: dict[str, Any]) -> None:
        active = dict(value.get("active_job", {}) or {})
        self.autonomy_rows["status"].set_value(display_status(value.get("status")))
        self.autonomy_rows["jobs"].set_value(value.get("job_count", 0))
        self.autonomy_rows["queue"].set_value(value.get("queued_count", 0))
        self.autonomy_rows["active"].set_value(active.get("title") or "BRAK")
        self.autonomy_rows["progress"].set_value(
            f"{active.get('completed_steps', 0)}/{active.get('total_steps', 0)} "
            f"({active.get('progress_percent', 0)}%)"
        )
        self.autonomy_rows["next"].set_value(active.get("next_step") or "BRAK")

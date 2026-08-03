from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill
from app.stability.controller import StabilitySuiteController


class StabilityBetaPage(QWidget):
    command_requested = Signal(str)

    def __init__(self, controller: StabilitySuiteController) -> None:
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
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)
        content.addWidget(self._scenario_card())
        content.addWidget(self._performance_card())
        content.addWidget(self._recovery_card())
        content.addWidget(self._restart_card())
        content.addWidget(self._beta_card())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)
        self.feedback = QLabel("Testy pozostają lokalne; brak automatycznej publikacji i zdalnego wykonywania kodu.")
        self.feedback.setObjectName("Muted")
        root.addWidget(self.feedback)
        self.refresh()

    def _toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("STABILNOŚĆ, ODZYSKIWANIE I BUSINESS BETA B111–B115")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Realne scenariusze, wydajność, recovery, bezpieczny restart i bramki Beta.")
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

    def _scenario_card(self) -> QWidget:
        card = SectionCard("B111 — Testy realnych scenariuszy", "Walidacja układu projektu, manifestu, zapisu raportów, usług i bezpiecznych ustawień.")
        self.scenario_rows = {
            "status": InfoRow("Status"), "runs": InfoRow("Uruchomienia"),
            "latest": InfoRow("Ostatni wynik"), "passed": InfoRow("Zaliczone"),
        }
        self._add_rows(card, self.scenario_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status B111"),
            ("URUCHOM TESTY", "Uruchom testy realnych scenariuszy B111"),
        ))
        return card

    def _performance_card(self) -> QWidget:
        card = SectionCard("B112 — Wydajność i porządkowanie", "Lokalne sondy czasu JSON, dysku i pamięci procesu bez ukrytych zmian systemowych.")
        self.performance_rows = {
            "status": InfoRow("Status"), "score": InfoRow("Wynik"),
            "ram": InfoRow("RAM procesu"), "json": InfoRow("JSON"), "file": InfoRow("Odczyt pliku"),
        }
        self._add_rows(card, self.performance_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status B112"),
            ("URUCHOM SONDĘ", "Uruchom test wydajności B112"),
            ("UPORZĄDKUJ", "Uporządkuj dane wydajności B112"),
        ))
        return card

    def _recovery_card(self) -> QWidget:
        card = SectionCard("B113 — Wykrywanie zawieszeń i recovery", "Heartbeat, wykrywanie niereagującej usługi i ograniczone przywrócenie stanu lokalnego.")
        self.recovery_rows = {
            "status": InfoRow("Status"), "services": InfoRow("Usługi"),
            "open": InfoRow("Otwarte incydenty"), "recoveries": InfoRow("Odzyskania"),
            "latest": InfoRow("Ostatni incydent"),
        }
        self._add_rows(card, self.recovery_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status B113"),
            ("SYMULUJ ZAWIESZENIE", "Symuluj zawieszenie usługi B113"),
            ("ODZYSKAJ", "Odzyskaj usługę B113"),
        ))
        return card

    def _restart_card(self) -> QWidget:
        card = SectionCard("B114 — Bezpieczny restart usług", "Jawny plan, checkpoint SHA-256, restart adaptera i weryfikacja przywróconego stanu.")
        self.restart_rows = {
            "status": InfoRow("Status"), "registered": InfoRow("Zarejestrowane usługi"),
            "plans": InfoRow("Plany"), "executions": InfoRow("Wykonania"),
            "restored": InfoRow("Stan przywrócony"),
        }
        self._add_rows(card, self.restart_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status B114"),
            ("PRZYGOTUJ", "Przygotuj restart usługi B114"),
            ("WYKONAJ", "Wykonaj restart usługi B114"),
        ))
        return card

    def _beta_card(self) -> QWidget:
        card = SectionCard("B115 — Business Beta", "Pięć twardych bramek; potwierdzenie właściciela nie publikuje ani nie wdraża programu automatycznie.")
        self.beta_rows = {
            "status": InfoRow("Status"), "audits": InfoRow("Audyty"),
            "latest": InfoRow("Ostatni audyt"), "gates": InfoRow("Bramki"),
            "ready": InfoRow("Business Beta"),
        }
        self._add_rows(card, self.beta_rows)
        card.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status B115"),
            ("AUDYT BETA", "Uruchom audyt Business Beta B115"),
            ("POTWIERDŹ BETA", "Potwierdź Business Beta B115"),
        ))
        return card

    @staticmethod
    def _add_rows(card: SectionCard, rows: dict[str, InfoRow]) -> None:
        for row in rows.values():
            card.content_layout.addWidget(row)

    def _actions(self, *buttons: tuple[str, str]) -> QHBoxLayout:
        layout = QHBoxLayout()
        for title, command in buttons:
            layout.addWidget(self._button(title, command))
        layout.addStretch(1)
        return layout

    def _button(self, title: str, command: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("SecondaryButton")
        button.clicked.connect(lambda _checked=False, value=command: self.command_requested.emit(value))
        return button

    def refresh(self) -> None:
        status = self.controller.status()
        self.overall.set_status("STABILNOŚĆ GOTOWA", "healthy")
        self._refresh_scenarios(dict(status.get("scenarios", {}) or {}))
        self._refresh_performance(dict(status.get("performance", {}) or {}))
        self._refresh_recovery(dict(status.get("recovery", {}) or {}))
        self._refresh_restart(dict(status.get("restart", {}) or {}))
        self._refresh_beta(dict(status.get("beta", {}) or {}))

    def _refresh_scenarios(self, value: dict[str, Any]) -> None:
        self.scenario_rows["status"].set_value(display_status(value.get("status")))
        self.scenario_rows["runs"].set_value(value.get("run_count", 0))
        self.scenario_rows["latest"].set_value(value.get("latest_status", "NOT_RUN"))
        self.scenario_rows["passed"].set_value(f"{value.get('latest_passed', 0)}/{value.get('latest_total', 0)}")

    def _refresh_performance(self, value: dict[str, Any]) -> None:
        self.performance_rows["status"].set_value(display_status(value.get("status")))
        self.performance_rows["score"].set_value(f"{value.get('latest_score', 0)}/100")
        self.performance_rows["ram"].set_value(f"{value.get('rss_mb', 0)} MB")
        self.performance_rows["json"].set_value(f"{value.get('json_roundtrip_ms', 0)} ms")
        self.performance_rows["file"].set_value(f"{value.get('file_read_ms', 0)} ms")

    def _refresh_recovery(self, value: dict[str, Any]) -> None:
        latest = dict(value.get("latest_incident", {}) or {})
        self.recovery_rows["status"].set_value(display_status(value.get("status")))
        self.recovery_rows["services"].set_value(value.get("service_count", 0))
        self.recovery_rows["open"].set_value(value.get("open_incident_count", 0))
        self.recovery_rows["recoveries"].set_value(value.get("recovery_count", 0))
        self.recovery_rows["latest"].set_value(latest.get("service") or "BRAK")

    def _refresh_restart(self, value: dict[str, Any]) -> None:
        self.restart_rows["status"].set_value(display_status(value.get("status")))
        self.restart_rows["registered"].set_value(", ".join(value.get("registered_services", [])) or "BRAK")
        self.restart_rows["plans"].set_value(value.get("plan_count", 0))
        self.restart_rows["executions"].set_value(value.get("execution_count", 0))
        self.restart_rows["restored"].set_value("TAK" if value.get("state_restored") else "NIE")

    def _refresh_beta(self, value: dict[str, Any]) -> None:
        self.beta_rows["status"].set_value(display_status(value.get("status")))
        self.beta_rows["audits"].set_value(value.get("audit_count", 0))
        self.beta_rows["latest"].set_value(value.get("latest_audit_status", "NOT_RUN"))
        self.beta_rows["gates"].set_value(f"{value.get('gates_passed', 0)}/{value.get('gates_total', 5)}")
        self.beta_rows["ready"].set_value("GOTOWA" if value.get("beta_ready") else "NIEGOTOWA")

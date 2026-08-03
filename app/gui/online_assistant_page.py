from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill
from app.gui.online_assistant_v13_panel import OnlineAssistantV13Panel


class OnlineAssistantPage(QWidget):
    """B126-B130 owner panel for explicit-consent Google Workspace operations."""

    command_requested = Signal(str)

    def __init__(self, controller: Any) -> None:
        super().__init__()
        self.controller = controller
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = SectionCard(
            "ASYSTENT ONLINE B126–B135 • BUSINESS 1.2 STABLE RC + 1.3 BETA",
            "Gmail, Kalendarz Google i Dysk Google działają dopiero po jawnej zgodzie OAuth. Każdy zapis i każda wysyłka nadal wymagają potwierdzenia.",
        )
        top = QHBoxLayout()
        self.overall = StatusPill("OCZEKUJE NA POŁĄCZENIE", "neutral")
        refresh = QPushButton("ODŚWIEŻ")
        refresh.setObjectName("SecondaryButton")
        refresh.clicked.connect(self.refresh)
        top.addWidget(self.overall)
        top.addStretch(1)
        top.addWidget(refresh)
        header.content_layout.addLayout(top)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.cards = QVBoxLayout(content)
        self.cards.setContentsMargins(0, 0, 0, 0)
        self.cards.setSpacing(10)

        self.connection_rows = {
            "status": InfoRow("Status"),
            "libraries": InfoRow("Biblioteki Google"),
            "client": InfoRow("OAuth Desktop client"),
            "token": InfoRow("Token lokalny"),
            "path": InfoRow("Wymagany plik"),
        }
        connection = SectionCard(
            "B126–B128 — POŁĄCZENIE GOOGLE WORKSPACE",
            "Połączenie otwiera systemową przeglądarkę. Token jest przechowywany wyłącznie lokalnie i nie jest pokazywany w interfejsie.",
        )
        self._add_rows(connection, self.connection_rows)
        connection.content_layout.addLayout(self._actions(
            ("STATUS", "Pokaż status asystenta online"),
            ("POŁĄCZ GOOGLE", "Połącz Google Workspace"),
            ("ROZŁĄCZ", "Rozłącz Google Workspace"),
        ))
        self.cards.addWidget(connection)

        self.gmail_rows = {
            "status": InfoRow("Status"),
            "connected": InfoRow("Połączony"),
            "operations": InfoRow("Operacje"),
            "last": InfoRow("Ostatnia operacja"),
            "sending": InfoRow("Automatyczna wysyłka"),
        }
        gmail = SectionCard(
            "B126 — PRAWDZIWY GMAIL",
            "Odczyt najnowszych i priorytetowych wiadomości, tworzenie szkiców oraz wysyłka istniejącego szkicu po potwierdzeniu.",
        )
        self._add_rows(gmail, self.gmail_rows)
        gmail.content_layout.addLayout(self._actions(
            ("NAJNOWSZE", "Pokaż najnowsze maile Gmail"),
            ("PRIORYTETOWE", "Pokaż priorytetowe maile Gmail"),
            ("SZKIC DEMO", "Utwórz szkic Gmail do example@example.com temat Test JARVIS treść To jest bezpieczny szkic testowy JARVIS OS."),
        ))
        self.cards.addWidget(gmail)

        self.calendar_rows = {
            "status": InfoRow("Status"),
            "connected": InfoRow("Połączony"),
            "operations": InfoRow("Operacje"),
            "last": InfoRow("Ostatnia operacja"),
        }
        calendar = SectionCard(
            "B127 — GOOGLE CALENDAR",
            "Plan dnia i konflikty są tylko odczytywane. Nowe wydarzenia wymagają potwierdzenia i nie wysyłają automatycznych zaproszeń.",
        )
        self._add_rows(calendar, self.calendar_rows)
        calendar.content_layout.addLayout(self._actions(
            ("DZISIAJ", "Pokaż Kalendarz Google na dziś"),
            ("KONFLIKTY", "Sprawdź konflikty Kalendarza Google"),
        ))
        self.cards.addWidget(calendar)

        self.drive_rows = {
            "status": InfoRow("Status"),
            "connected": InfoRow("Połączony"),
            "operations": InfoRow("Operacje"),
            "last": InfoRow("Ostatnia operacja"),
            "limit": InfoRow("Limit lokalnego odczytu"),
        }
        drive = SectionCard(
            "B128 — GOOGLE DRIVE I DOKUMENTY",
            "Wyszukiwanie metadanych, ograniczony odczyt tekstu i zapis raportów utworzonych przez JARVIS OS.",
        )
        self._add_rows(drive, self.drive_rows)
        drive.content_layout.addLayout(self._actions(
            ("SZUKAJ JARVIS", "Wyszukaj na Dysku Google JARVIS"),
            ("ZAPISZ RAPORT", "Zapisz raport na Dysku Google"),
        ))
        self.cards.addWidget(drive)

        self.day_rows = {
            "status": InfoRow("Status"),
            "snapshots": InfoRow("Podsumowania"),
            "mail": InfoRow("Priorytetowe wiadomości"),
            "events": InfoRow("Dzisiejsze wydarzenia"),
            "reminders": InfoRow("Lokalne przypomnienia"),
        }
        day = SectionCard(
            "B129 — WSPÓLNE CENTRUM DNIA ONLINE",
            "Jedno podsumowanie łączy Gmail, Kalendarz Google i lokalne przypomnienia bez działania w tle.",
        )
        self._add_rows(day, self.day_rows)
        day.content_layout.addLayout(self._actions(
            ("POKAŻ MÓJ DZIEŃ", "Pokaż centrum dnia online"),
        ))
        self.cards.addWidget(day)

        self.rc_rows = {
            "status": InfoRow("Status"),
            "audits": InfoRow("Audyty"),
            "latest": InfoRow("Ostatni audyt"),
            "gates": InfoRow("Bramki"),
            "ready": InfoRow("Stable RC"),
            "publication": InfoRow("Automatyczna publikacja"),
        }
        rc = SectionCard(
            "B130 — BUSINESS 1.2 STABLE RC",
            "Stable RC można potwierdzić dopiero po prawdziwym połączeniu i zaliczeniu odczytu Gmail, Kalendarza i Dysku.",
        )
        self._add_rows(rc, self.rc_rows)
        rc.content_layout.addLayout(self._actions(
            ("AUDYT RC", "Uruchom audyt Business 1.2 Stable RC"),
            ("POTWIERDŹ RC", "Potwierdź Business 1.2 Stable RC"),
        ))
        self.cards.addWidget(rc)
        self.v13_panel = OnlineAssistantV13Panel(self.controller.v13)
        self.v13_panel.command_requested.connect(self.command_requested.emit)
        self.cards.addWidget(self.v13_panel)
        self.cards.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

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
        if hasattr(self, "v13_panel"):
            self.v13_panel.refresh()
        connection = dict(status.get("connection", {}) or {})
        connected = bool(connection.get("token_present"))
        rc = dict(status.get("rc", {}) or {})
        self.overall.set_status(
            "BUSINESS 1.2 STABLE RC" if rc.get("rc_ready") else (
                "GOOGLE POŁĄCZONE" if connected else "OCZEKUJE NA POŁĄCZENIE"
            ),
            "healthy" if connected else "neutral",
        )
        self.connection_rows["status"].set_value(display_status(connection.get("status")))
        self.connection_rows["libraries"].set_value("GOTOWE" if connection.get("dependency_ready") else "BRAK")
        self.connection_rows["client"].set_value("GOTOWY" if connection.get("client_configured") else "BRAK")
        self.connection_rows["token"].set_value("TAK" if connection.get("token_present") else "NIE")
        self.connection_rows["path"].set_value(connection.get("client_config_path") or "BRAK")

        gmail = dict(status.get("gmail", {}) or {})
        self.gmail_rows["status"].set_value(display_status(gmail.get("status")))
        self.gmail_rows["connected"].set_value("TAK" if gmail.get("connected") else "NIE")
        self.gmail_rows["operations"].set_value(gmail.get("operation_count", 0))
        self.gmail_rows["last"].set_value(dict(gmail.get("last_operation", {}) or {}).get("action") or "BRAK")
        self.gmail_rows["sending"].set_value("WYŁĄCZONA")

        calendar = dict(status.get("calendar", {}) or {})
        self.calendar_rows["status"].set_value(display_status(calendar.get("status")))
        self.calendar_rows["connected"].set_value("TAK" if calendar.get("connected") else "NIE")
        self.calendar_rows["operations"].set_value(calendar.get("operation_count", 0))
        self.calendar_rows["last"].set_value(dict(calendar.get("last_operation", {}) or {}).get("action") or "BRAK")

        drive = dict(status.get("drive", {}) or {})
        self.drive_rows["status"].set_value(display_status(drive.get("status")))
        self.drive_rows["connected"].set_value("TAK" if drive.get("connected") else "NIE")
        self.drive_rows["operations"].set_value(drive.get("operation_count", 0))
        self.drive_rows["last"].set_value(dict(drive.get("last_operation", {}) or {}).get("action") or "BRAK")
        self.drive_rows["limit"].set_value(f"{drive.get('max_read_characters', 0)} znaków")

        day = dict(status.get("day_center", {}) or {})
        latest = dict(day.get("latest", {}) or {})
        self.day_rows["status"].set_value(display_status(day.get("status")))
        self.day_rows["snapshots"].set_value(day.get("snapshot_count", 0))
        self.day_rows["mail"].set_value(latest.get("priority_mail_count", 0))
        self.day_rows["events"].set_value(latest.get("today_event_count", 0))
        self.day_rows["reminders"].set_value(latest.get("pending_reminders", 0))

        self.rc_rows["status"].set_value(display_status(rc.get("status")))
        self.rc_rows["audits"].set_value(rc.get("audit_count", 0))
        self.rc_rows["latest"].set_value(rc.get("latest_audit_status", "NOT_RUN"))
        self.rc_rows["gates"].set_value(f"{rc.get('gates_passed', 0)}/{rc.get('gates_total', 10)}")
        self.rc_rows["ready"].set_value("GOTOWY" if rc.get("rc_ready") else "OCZEKUJE")
        self.rc_rows["publication"].set_value("WYŁĄCZONA")

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.gui.business_display import display_status
from app.gui.business_widgets import InfoRow, SectionCard, StatusPill
from app.productivity.controller import ProductivitySuiteController


class ProductivityCenterPage(QWidget):
    command_requested = Signal(str)

    def __init__(self, controller: ProductivitySuiteController) -> None:
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
        content.addWidget(self._mail_card())
        content.addWidget(self._calendar_card())
        content.addWidget(self._document_card())
        content.addWidget(self._reminder_card())
        content.addWidget(self._report_card())
        content.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)
        self.feedback = QLabel("Wszystkie dane pozostają lokalne; brak automatycznej wysyłki i synchronizacji chmurowej.")
        self.feedback.setObjectName("Muted")
        root.addWidget(self.feedback)
        self.refresh()

    def _toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("PRODUKTYWNOŚĆ I ORGANIZACJA B106–B110")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Lokalne szkice, kalendarz, dokumenty, przypomnienia i raport dnia.")
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

    def _mail_card(self) -> QWidget:
        card = SectionCard("B106 — Lokalne centrum poczty", "Szkice, priorytety i eksport EML; bez ukrytego wysyłania przez internet.")
        self.mail_rows = {
            "status": InfoRow("Status"), "drafts": InfoRow("Szkice"),
            "ready": InfoRow("Gotowe do eksportu"), "exported": InfoRow("Wyeksportowane"),
            "active": InfoRow("Aktywny temat"), "remote": InfoRow("Wysyłka zdalna"),
        }
        for row in self.mail_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("STATUS", "Pokaż status poczty B106"))
        actions.addWidget(self._button("UTWÓRZ DEMO", "Utwórz szkic email demo"))
        actions.addWidget(self._button("OZNACZ GOTOWY", "Oznacz szkic gotowy"))
        actions.addWidget(self._button("EKSPORTUJ EML", "Eksportuj szkic email"))
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _calendar_card(self) -> QWidget:
        card = SectionCard("B107 — Kalendarz i plan dnia", "Lokalne wydarzenia, najbliższy termin i wykrywanie nakładających się spotkań.")
        self.calendar_rows = {
            "status": InfoRow("Status"), "events": InfoRow("Wydarzenia"),
            "upcoming": InfoRow("Nadchodzące"), "conflicts": InfoRow("Konflikty"),
            "next": InfoRow("Następne wydarzenie"), "timezone": InfoRow("Strefa"),
        }
        for row in self.calendar_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("STATUS", "Pokaż status kalendarza B107"))
        actions.addWidget(self._button("DODAJ DEMO", "Dodaj spotkanie demo"))
        actions.addWidget(self._button("SPRAWDŹ KONFLIKTY", "Sprawdź konflikty kalendarza"))
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _document_card(self) -> QWidget:
        card = SectionCard("B108 — Dokumenty i foldery", "Bezpieczny lokalny indeks plików z AI_PLIKI, metadanymi i wyszukiwaniem.")
        self.document_rows = {
            "status": InfoRow("Status"), "documents": InfoRow("Dokumenty"),
            "text": InfoRow("Treść zindeksowana"), "scan": InfoRow("Ostatni skan"),
            "query": InfoRow("Ostatnie wyszukiwanie"), "results": InfoRow("Trafienia"),
        }
        for row in self.document_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("STATUS", "Pokaż status dokumentów B108"))
        actions.addWidget(self._button("UTWÓRZ DEMO", "Utwórz dokument demo"))
        actions.addWidget(self._button("SKANUJ", "Skanuj dokumenty"))
        actions.addWidget(self._button("ZNAJDŹ JARVIS", "Znajdź dokument: JARVIS"))
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _reminder_card(self) -> QWidget:
        card = SectionCard("B109 — Przypomnienia 2.0", "Jednorazowe i cykliczne przypomnienia z terminem, stanem i jawnym zakończeniem.")
        self.reminder_rows = {
            "status": InfoRow("Status"), "all": InfoRow("Wszystkie"),
            "pending": InfoRow("Oczekujące"), "due": InfoRow("Pilne"),
            "recurring": InfoRow("Cykliczne"), "next": InfoRow("Następne"),
        }
        for row in self.reminder_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("STATUS", "Pokaż status przypomnień 2 B109"))
        actions.addWidget(self._button("DODAJ DEMO", "Dodaj przypomnienie B109 demo"))
        actions.addWidget(self._button("ZAKOŃCZ", "Zakończ przypomnienie B109"))
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _report_card(self) -> QWidget:
        card = SectionCard("B110 — Raport dnia i plan jutra", "Jedno lokalne podsumowanie B106–B109 oraz plan następnego dnia do AI_PLIKI.")
        self.report_rows = {
            "status": InfoRow("Status"), "reports": InfoRow("Raporty"),
            "latest": InfoRow("Ostatni raport"), "plan": InfoRow("Punkty planu"),
            "preview": InfoRow("Ostatni podgląd"),
        }
        for row in self.report_rows.values():
            card.content_layout.addWidget(row)
        actions = QHBoxLayout()
        actions.addWidget(self._button("STATUS", "Pokaż status raportu produktywności B110"))
        actions.addWidget(self._button("GENERUJ RAPORT", "Generuj raport dnia B110"))
        actions.addStretch(1)
        card.content_layout.addLayout(actions)
        return card

    def _button(self, title: str, command: str) -> QPushButton:
        button = QPushButton(title)
        button.setObjectName("SecondaryButton")
        button.clicked.connect(lambda _checked=False, value=command: self.command_requested.emit(value))
        return button

    def refresh(self) -> None:
        status = self.controller.status()
        self.overall.set_status("PRODUKTYWNOŚĆ GOTOWA", "healthy")
        self._refresh_mail(dict(status.get("mail", {}) or {}))
        self._refresh_calendar(dict(status.get("calendar", {}) or {}))
        self._refresh_documents(dict(status.get("documents", {}) or {}))
        self._refresh_reminders(dict(status.get("reminders", {}) or {}))
        self._refresh_reporting(dict(status.get("reporting", {}) or {}))

    def _refresh_mail(self, value: dict[str, Any]) -> None:
        active = dict(value.get("active_draft", {}) or {})
        self.mail_rows["status"].set_value(display_status(value.get("status")))
        self.mail_rows["drafts"].set_value(value.get("draft_count", 0))
        self.mail_rows["ready"].set_value(value.get("ready_count", 0))
        self.mail_rows["exported"].set_value(value.get("exported_count", 0))
        self.mail_rows["active"].set_value(active.get("subject") or "BRAK")
        self.mail_rows["remote"].set_value("WYŁĄCZONA")

    def _refresh_calendar(self, value: dict[str, Any]) -> None:
        next_event = dict(value.get("next_event", {}) or {})
        self.calendar_rows["status"].set_value(display_status(value.get("status")))
        self.calendar_rows["events"].set_value(value.get("event_count", 0))
        self.calendar_rows["upcoming"].set_value(value.get("upcoming_count", 0))
        self.calendar_rows["conflicts"].set_value(value.get("conflict_count", 0))
        self.calendar_rows["next"].set_value(next_event.get("title") or "BRAK")
        self.calendar_rows["timezone"].set_value(value.get("timezone", "UTC"))

    def _refresh_documents(self, value: dict[str, Any]) -> None:
        self.document_rows["status"].set_value(display_status(value.get("status")))
        self.document_rows["documents"].set_value(value.get("document_count", 0))
        self.document_rows["text"].set_value(value.get("text_document_count", 0))
        self.document_rows["scan"].set_value(value.get("last_scan_path") or "BRAK")
        self.document_rows["query"].set_value(value.get("last_query") or "BRAK")
        self.document_rows["results"].set_value(value.get("last_result_count", 0))

    def _refresh_reminders(self, value: dict[str, Any]) -> None:
        next_reminder = dict(value.get("next_reminder", {}) or {})
        self.reminder_rows["status"].set_value(display_status(value.get("status")))
        self.reminder_rows["all"].set_value(value.get("reminder_count", 0))
        self.reminder_rows["pending"].set_value(value.get("pending_count", 0))
        self.reminder_rows["due"].set_value(value.get("due_count", 0))
        self.reminder_rows["recurring"].set_value(value.get("recurring_count", 0))
        self.reminder_rows["next"].set_value(next_reminder.get("text") or "BRAK")

    def _refresh_reporting(self, value: dict[str, Any]) -> None:
        latest = dict(value.get("latest_report", {}) or {})
        self.report_rows["status"].set_value(display_status(value.get("status")))
        self.report_rows["reports"].set_value(value.get("report_count", 0))
        self.report_rows["latest"].set_value(latest.get("text_path") or "BRAK")
        self.report_rows["plan"].set_value(value.get("plan_item_count", 0))
        self.report_rows["preview"].set_value(value.get("generated_preview_at") or "BRAK")

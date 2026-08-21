"""Read-only owner dashboard for autonomous local Forex PAPER positions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.business_widgets import MetricCard, SectionCard, StatusPill


class ForexPaperPage(QWidget):
    """Display current PAPER positions without exposing execution controls."""

    REFRESH_INTERVAL_MS = 5000
    HEADERS = ("PARA", "KIERUNEK", "JEDNOSTKI", "WEJŚCIE", "CENA", "STOP LOSS", "TAKE PROFIT")

    def __init__(self, dashboard: Any) -> None:
        super().__init__()
        self.dashboard = dashboard
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(self._toolbar())
        root.addLayout(self._metrics())
        root.addWidget(self._positions_card(), 1)
        root.addWidget(self._safety_card())
        self.timer = QTimer(self)
        self.timer.setInterval(self.REFRESH_INTERVAL_MS)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def _toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("PageToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(14, 10, 14, 10)
        heading = QVBoxLayout()
        title = QLabel("FOREX PAPER — OTWARTE POZYCJE")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Automatycznie odświeżany podgląd lokalnej symulacji JARVIS OS."
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

    def _metrics(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setSpacing(10)
        self.metrics = {
            "balance": MetricCard("SALDO PAPER", "—", "PLN"),
            "equity": MetricCard("WARTOŚĆ KONTA", "—", "PLN"),
            "unrealized": MetricCard("WYNIK OTWARTY", "—", "PLN"),
            "positions": MetricCard("POZYCJE", "0", "PAPER"),
        }
        for column, card in enumerate(self.metrics.values()):
            layout.addWidget(card, 0, column)
        return layout

    def _positions_card(self) -> SectionCard:
        card = SectionCard(
            "Pozycje zarządzane przez JARVIS",
            "Panel jest wyłącznie informacyjny; strategia zarządza SL i TP w lokalnej księdze PAPER.",
        )
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setObjectName("ForexPaperPositions")
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #08101C;
                alternate-background-color: #0B1626;
                color: #E8EEF8;
                border: 1px solid #22314A;
                border-radius: 8px;
                selection-background-color: #174B66;
                selection-color: #FFFFFF;
                outline: none;
            }
            QTableWidget::item {
                border-bottom: 1px solid #17263D;
                padding: 7px;
            }
            QHeaderView::section {
                background-color: #111D2F;
                color: #8FDCFF;
                border: none;
                border-right: 1px solid #22314A;
                border-bottom: 1px solid #2B4568;
                padding: 8px;
                font-weight: 700;
            }
            QTableCornerButton::section {
                background-color: #111D2F;
                border: none;
            }
        """)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setMinimumHeight(190)
        card.content_layout.addWidget(self.table)
        self.updated = QLabel("Ostatnia aktualizacja: —")
        self.updated.setObjectName("Muted")
        card.content_layout.addWidget(self.updated)
        return card

    def _safety_card(self) -> SectionCard:
        card = SectionCard("Bezpieczeństwo", "Prawdziwe zlecenia pozostają twardo wyłączone.")
        self.safety = QLabel(
            "● PAPER ONLY   ● BROKER: BRAK ZLECEŃ   ● PRAWDZIWE PIENIĄDZE: BRAK DOSTĘPU"
        )
        self.safety.setObjectName("Healthy")
        self.safety.setWordWrap(True)
        card.content_layout.addWidget(self.safety)
        self.message = QLabel("Gotowy.")
        self.message.setObjectName("Muted")
        self.message.setWordWrap(True)
        card.content_layout.addWidget(self.message)
        return card

    def refresh(self) -> None:
        try:
            value = self.dashboard.snapshot()
            snapshot = dict(value) if isinstance(value, dict) else {}
        except Exception:
            snapshot = {"status": "BLOCKED", "positions": [], "message": "Podgląd jest chwilowo niedostępny."}
        ready = snapshot.get("status") == "READY"
        self.overall.set_status(
            "PAPER AKTYWNY" if ready else "WYMAGA UWAGI",
            "healthy" if ready else "danger",
        )
        self.metrics["balance"].set_value(f"{snapshot.get('balance_pln', '0.00')} PLN")
        self.metrics["equity"].set_value(f"{snapshot.get('equity_pln', '0.00')} PLN")
        pnl = str(snapshot.get("unrealized_pnl_pln", "0.00"))
        self.metrics["unrealized"].set_value(f"{pnl} PLN")
        self.metrics["unrealized"].set_hint(self._pnl_hint(pnl))
        raw_positions = snapshot.get("positions")
        raw_positions = raw_positions if isinstance(raw_positions, list) else []
        positions = [dict(item) for item in raw_positions[:5] if isinstance(item, dict)]
        self.metrics["positions"].set_value(str(len(positions)))
        self._fill_positions(positions)
        self.updated.setText(
            "Ostatnia aktualizacja: " + self._visible_time(snapshot.get("observed_at"))
        )
        self.message.setText(str(snapshot.get("message", "Gotowy."))[:240])

    def _fill_positions(self, positions: list[dict[str, Any]]) -> None:
        self.table.clearSpans()
        if not positions:
            self.table.setRowCount(1)
            item = QTableWidgetItem("BRAK OTWARTYCH POZYCJI PAPER")
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 0, item)
            self.table.setSpan(0, 0, 1, len(self.HEADERS))
            return
        self.table.setRowCount(len(positions))
        keys = ("pair", "side", "units", "entry_price", "current_price", "stop_loss", "take_profit")
        for row, position in enumerate(positions):
            values = [str(position.get(key, "—")) for key in keys]
            values[0] = values[0].replace("_", "/")
            values[1] = "KUPNO / LONG" if values[1] == "LONG" else "SPRZEDAŻ / SHORT"
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)

    @staticmethod
    def _visible_time(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return "lokalna księga"
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            return text[:32]

    @staticmethod
    def _pnl_hint(value: object) -> str:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            number = Decimal("0")
        if not number.is_finite():
            number = Decimal("0")
        if number > 0:
            return "ZYSK"
        if number < 0:
            return "STRATA"
        return "BEZ ZMIAN"


__all__ = ["ForexPaperPage"]

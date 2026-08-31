"""Read-only seven-pair PAPER performance table."""

from __future__ import annotations

from typing import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


class ForexPairResultsTable(QTableWidget):
    """Render sanitized PAPER metrics without any execution controls."""

    PAIRS = (
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "AUD_USD",
        "USD_CAD",
        "NZD_USD",
    )
    HEADERS = (
        "PARA",
        "ZAMKNIĘTE",
        "WYGRANE",
        "PRZEGRANE",
        "WIN RATE",
        "WYNIK PLN",
        "ŚREDNIA PLN",
        "PROFIT FACTOR",
        "POSTĘP",
        "STATUS",
    )

    def __init__(self) -> None:
        super().__init__(0, len(self.HEADERS))
        self.setObjectName("ForexPaperPairResults")
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def set_values(self, values: Mapping[str, object]) -> None:
        self.setRowCount(len(self.PAIRS))
        for row, pair in enumerate(self.PAIRS):
            raw = values.get(pair)
            metrics = dict(raw) if isinstance(raw, Mapping) else {}
            factor = metrics.get("profit_factor")
            review_status = {
                "NO_CLOSED_TRADES": "BRAK DANYCH",
                "COLLECTING_PAIR_SAMPLE": "ZBIERANIE",
                "READY_FOR_MANUAL_REVIEW": "DO PRZEGLĄDU",
                "BLOCKED_INVALID_EVIDENCE": "BLOKADA DOWODÓW",
            }.get(str(metrics.get("review_status", "")), "BRAK DANYCH")
            columns = (
                pair.replace("_", "/"),
                str(metrics.get("closed_trade_count", 0)),
                str(metrics.get("winning_trade_count", 0)),
                str(metrics.get("losing_trade_count", 0)),
                f"{metrics.get('win_rate_pct', '0.00')}%",
                str(metrics.get("net_realized_pnl_pln", "0.00")),
                str(metrics.get("average_trade_pnl_pln", "0.00")),
                str(factor) if factor is not None else "N/D",
                (
                    f"{metrics.get('closed_trade_count', 0)}/"
                    f"{metrics.get('minimum_closed_trades_for_review', 20)}"
                ),
                review_status,
            )
            for column, value in enumerate(columns):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, column, item)


__all__ = ["ForexPairResultsTable"]

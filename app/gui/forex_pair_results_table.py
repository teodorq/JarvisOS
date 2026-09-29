"""Read-only seven-pair PAPER performance table."""

from __future__ import annotations

from typing import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


def _count(value: object) -> int:
    try:
        return max(0, min(int(value or 0), 1_000_000))
    except (TypeError, ValueError):
        return 0


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
        "PRÓBKA",
        "WYGRANE",
        "PRZEGRANE",
        "WIN RATE",
        "WYNIK PLN",
        "ŚREDNIA PLN",
        "PROFIT FACTOR",
        "POSTĘP",
        "STATUS",
        "DANE R",
        "ŚREDNIA R",
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
            raw_risk = metrics.get("risk_diagnostics")
            risk = dict(raw_risk) if isinstance(raw_risk, Mapping) else {}
            risk_count = _count(risk.get("risk_observed_trade_count"))
            risk_total = _count(risk.get("closed_trade_count"))
            recorded_r = _count(risk.get("realized_r_recorded_trade_count"))
            derived_r = _count(risk.get("realized_r_derived_trade_count"))
            mismatched_r = _count(risk.get("realized_r_mismatch_count"))
            risk_coverage = risk.get("risk_coverage_pct", "0.00")
            average_r = risk.get("average_r_multiple")
            risk_provenance = (
                f"Zapisane przy zamknięciu: {recorded_r}. "
                f"Wyliczone kontrolnie ze starszych zapisów: {derived_r}. "
                f"Niezgodności: {mismatched_r}."
            )
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
                    f"{metrics.get('sample_contract_closed_trade_count', metrics.get('closed_trade_count', 0))}/"
                    f"{metrics.get('minimum_closed_trades_for_review', 20)}"
                ),
                review_status,
                f"{risk_count}/{risk_total} ({risk_coverage}%)",
                str(average_r) if average_r is not None else "N/D",
            )
            for column, value in enumerate(columns):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if column == 10:
                    item.setToolTip(risk_provenance)
                self.setItem(row, column, item)


__all__ = ["ForexPairResultsTable"]

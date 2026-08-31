from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.gui.forex_paper_page import ForexPaperPage


class _Dashboard:
    def snapshot(self) -> dict:
        return {
            "status": "READY",
            "observed_at": "2026-08-21T10:09:38+00:00",
            "balance_pln": "100000.00",
            "equity_pln": "99998.12",
            "unrealized_pnl_pln": "-1.88",
            "performance": {
                "valid_closed_trade_count": 1,
                "minimum_closed_trades_for_review": 20,
                "average_trade_pnl_pln": "-44.26",
                "profit_factor": "0.0000",
                "maximum_closed_trade_drawdown_pln": "44.26",
                "maximum_closed_trade_drawdown_pct": "0.04",
                "pair_breakdown": {
                    "USD_CHF": {
                        "closed_trade_count": 1,
                        "winning_trade_count": 0,
                        "losing_trade_count": 1,
                        "win_rate_pct": "0.00",
                        "net_realized_pnl_pln": "-44.26",
                        "average_trade_pnl_pln": "-44.26",
                        "profit_factor": "0.0000",
                        "minimum_closed_trades_for_review": 20,
                        "review_status": "COLLECTING_PAIR_SAMPLE",
                    },
                },
            },
            "pair_review": {
                "ready_pair_count": 0,
                "collecting_pair_count": 1,
                "unobserved_pair_count": 6,
            },
            "positions": [{
                "pair": "USD_CHF",
                "side": "SHORT",
                "units": "2714",
                "entry_price": "0.799040",
                "current_price": "0.799040",
                "stop_loss": "0.800040",
                "take_profit": "0.797040",
            }],
            "loss_streak_safety": {
                "active": True,
                "current_consecutive_losses": 3,
                "threshold": 3,
            },
            "message": "Lokalna symulacja; brak zleceń u brokera.",
        }


class _Activity:
    def history(self, *, limit: int = 50) -> list[dict]:
        assert limit == 50
        return [{
            "sequence": 1,
            "occurred_at": "2026-08-21T10:09:38+00:00",
            "kind": "POSITION_OPENED",
            "message": "Forex PAPER: otworzyłem pozycję SHORT na USD/CHF.",
            "delivered": False,
            "delivery_status": "OCZEKUJE",
        }]


def test_forex_page_shows_position_and_has_no_execution_controls() -> None:
    app = QApplication.instance() or QApplication([])
    page = ForexPaperPage(_Dashboard(), activity=_Activity())
    try:
        assert page.table.rowCount() == 1
        assert page.table.item(0, 0).text() == "USD/CHF"
        assert page.table.item(0, 1).text() == "SPRZEDAŻ / SHORT"
        assert page.table.item(0, 5).text() == "0.800040"
        assert page.metrics["unrealized"].value_label.text() == "-1.88 PLN"
        assert page.metrics["closed"].value_label.text() == "1 / 20"
        assert page.metrics["average"].value_label.text() == "-44.26 PLN"
        assert page.metrics["profit_factor"].value_label.text() == "0.0000"
        assert page.metrics["drawdown"].value_label.text() == "44.26 PLN"
        assert page.tabs.count() == 3
        assert page.pair_table.rowCount() == 7
        assert page.pair_table.item(3, 0).text() == "USD/CHF"
        assert page.pair_table.item(3, 1).text() == "1"
        assert page.pair_table.item(3, 5).text() == "-44.26"
        assert page.pair_table.item(3, 7).text() == "0.0000"
        assert page.pair_table.item(3, 8).text() == "1/20"
        assert page.pair_table.item(3, 9).text() == "ZBIERANIE"
        assert page.history_table.rowCount() == 1
        assert page.history_table.item(0, 1).text() == "OTWARCIE"
        assert page.history_table.item(0, 3).text() == "OCZEKUJE"
        assert page.pending_history.text() == "Nieodczytane zdarzenia: 1"
        assert page.overall.full_text == "PAPER — PRZERWA"
        assert "NOWE WEJŚCIA: PRZERWA" in page.safety.text()
        labels = [button.text() for button in page.findChildren(QPushButton)]
        assert labels == ["ODŚWIEŻ"]
    finally:
        page.timer.stop()
        page.deleteLater()
        app.processEvents()


def test_main_window_exposes_forex_page_without_exceeding_limit() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "app" / "gui" / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "ForexPaperPage" in source
    assert '("FOREX PAPER", "forex")' in source
    assert '"forex": self.forex_page' in source
    assert "activity=self.assistant.trading.forex_activity" in source
    assert len(source.splitlines()) < 440

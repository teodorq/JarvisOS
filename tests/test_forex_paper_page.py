from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.gui.forex_paper_page import ForexPaperPage
from app.gui.forex_performance_review_view import forex_performance_review_view
from app.gui.forex_paper_safety_view import forex_paper_safety_view
from app.gui.forex_paper_safety_view import forex_paper_safety_view
from app.gui.forex_runtime_cycle_view import forex_runtime_cycle_text
from app.gui.forex_v2_research_view import forex_v2_research_text


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
                "risk_diagnostics": {
                    "status": "NO_RISK_TELEMETRY",
                    "closed_trade_count": 1,
                    "risk_observed_trade_count": 0,
                    "risk_missing_trade_count": 1,
                    "risk_coverage_pct": "0.00",
                    "net_r_multiple": None,
                    "average_r_multiple": None,
                },
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
            "performance_review": {
                "status": "WAITING_FOR_PAPER_SAMPLE",
                "source_valid": True,
                "valid_closed_trade_count": 1,
                "minimum_closed_trades_for_review": 20,
                "remaining_closed_trades_for_review": 19,
                "packet_persisted": False,
                "review_snapshot_frozen": False,
                "live_activation_ready": False,
            },
            "v2_research": {
                "status": "READY_FOR_OWNER_REVIEW",
                "source_valid": True,
                "accepted_cycle_count": 20,
                "minimum_accepted_cycle_count": 20,
                "accepted_market_day_count": 4,
                "minimum_market_day_count": 3,
                "base_entry_signal_count": 1,
                "retained_entry_signal_count": 0,
                "filtered_entry_signal_count": 1,
                "packet_persisted": True,
                "review_snapshot_frozen": True,
            },
            "last_runtime_cycle": {
                "available": True,
                "status": "PAPER_CYCLE_COMPLETED",
                "decision": "NO_ENTRY_SIGNAL",
                "ready_pair_count": 7,
                "blocked_pair_count": 0,
                "execution_count": 0,
                "reason_codes": {
                    "NO_NEW_CROSSOVER": 6,
                    "LONG_TREND_INTACT": 1,
                },
                "high_impact_event_window": False,
                "live_orders_sent": False,
                "real_money_access": False,
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
                "initial_risk_pln": "8.01",
                "risk_recorded": True,
            }],
            "loss_streak_safety": {
                "active": True,
                "current_consecutive_losses": 3,
                "threshold": 3,
            },
            "message": "Lokalna symulacja; brak zleceń u brokera.",
            "position_protection": {
                "available": True,
                "status": "NO_PROTECTION_TRIGGER",
                "reason": "",
                "consecutive_failure_count": 0,
                "attention_required": False,
                "stale": False,
                "market_window_open": True,
            },
        }


class _Activity:
    def history(self, *, limit: int = 50) -> list[dict]:
        assert limit == 50
        return [
            {
                "sequence": 1,
                "occurred_at": "2026-08-21T10:09:38+00:00",
                "kind": "POSITION_OPENED",
                "message": "Forex PAPER: otworzyłem pozycję SHORT na USD/CHF.",
                "delivered": False,
                "delivery_status": "OCZEKUJE",
            },
            {
                "sequence": 2,
                "occurred_at": "2026-08-21T10:12:38+00:00",
                "kind": "POSITION_PROTECTION_ATTENTION",
                "message": "Ochrona SL/TP wymaga uwagi.",
                "delivered": False,
                "delivery_status": "OCZEKUJE",
            },
        ]


def test_forex_page_shows_position_and_has_no_execution_controls() -> None:
    app = QApplication.instance() or QApplication([])
    page = ForexPaperPage(_Dashboard(), activity=_Activity())
    try:
        assert page.table.rowCount() == 1
        assert page.table.item(0, 0).text() == "USD/CHF"
        assert page.table.item(0, 1).text() == "SPRZEDAŻ / SHORT"
        assert page.table.item(0, 5).text() == "0.800040"
        assert page.table.item(0, 7).text() == "8.01 PLN"
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
        assert page.history_table.rowCount() == 2
        assert page.history_table.item(0, 1).text() == "OCHRONA SL/TP — UWAGA"
        assert page.history_table.item(1, 1).text() == "OTWARCIE"
        assert page.history_table.item(0, 3).text() == "OCZEKUJE"
        assert page.pending_history.text() == "Nieodczytane zdarzenia: 2"
        assert page.overall.full_text == "PAPER — PRZERWA"
        assert page.protection.full_text == "OCHRONA: DZIAŁA"
        assert page.sample_review.full_text == "PRÓBKA: 1/20"
        assert "niezmienny materiał" in page.performance_review_detail.text()
        assert "Dane R: 0/1" in page.performance_review_detail.text()
        assert "niczego nie szacuje" in page.performance_review_detail.text()
        assert "sygnały bazowe 1" in page.v2_research_detail.text()
        assert "nie wynik" in page.v2_research_detail.text()
        assert "brak nowego sygnału wejścia" in page.message.text()
        assert "brak nowego przecięcia średnich: 6" in page.message.text()
        assert "brak działania" in page.protection_detail.text()
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


def test_safety_banner_shows_weekly_loss_pause() -> None:
    label, tone, banner = forex_paper_safety_view({
        "status": "READY",
        "loss_streak_safety": {"active": False},
        "weekly_loss_safety": {"active": True},
    })

    assert label == "PAPER — PRZERWA"
    assert tone == "neutral"
    assert "LIMIT TYGODNIOWY" in banner


def test_performance_review_view_marks_frozen_packet_as_manual_only() -> None:
    label, tone, detail = forex_performance_review_view({
        "status": "READY_FOR_OWNER_REVIEW",
        "source_valid": True,
        "packet_persisted": True,
        "review_snapshot_frozen": True,
    })

    assert label == "PRÓBKA: ZAMROŻONA"
    assert tone == "healthy"
    assert "ręcznego przeglądu" in detail


def test_performance_review_view_explains_partial_risk_coverage() -> None:
    label, tone, detail = forex_performance_review_view(
        {
            "status": "WAITING_FOR_PAPER_SAMPLE",
            "source_valid": True,
            "valid_closed_trade_count": 4,
            "minimum_closed_trades_for_review": 20,
        },
        {
            "risk_diagnostics": {
                "closed_trade_count": 4,
                "risk_observed_trade_count": 3,
                "risk_missing_trade_count": 1,
                "risk_coverage_pct": "75.00",
                "net_r_multiple": "1.2500",
                "average_r_multiple": "0.4167",
            },
        },
    )

    assert label == "PRÓBKA: 4/20"
    assert tone == "accent"
    assert "Dane R: 3/4 (75.00%)" in detail
    assert "suma 1.2500 R" in detail
    assert "1 R oznacza początkowe ryzyko pozycji" in detail
    assert "nie szacuje" in detail


def test_v2_research_text_does_not_call_signal_sample_a_result() -> None:
    text = forex_v2_research_text({
        "status": "READY_FOR_OWNER_REVIEW",
        "source_valid": True,
        "accepted_cycle_count": 20,
        "minimum_accepted_cycle_count": 20,
        "accepted_market_day_count": 4,
        "minimum_market_day_count": 3,
        "base_entry_signal_count": 1,
        "retained_entry_signal_count": 0,
        "filtered_entry_signal_count": 1,
        "packet_persisted": True,
        "review_snapshot_frozen": True,
    })

    assert "zamrożone" in text
    assert "sygnały bazowe 1" in text
    assert "nie wynik ani potwierdzenie skuteczności" in text


def test_runtime_cycle_text_translates_safe_reason_counts() -> None:
    text = forex_runtime_cycle_text({
        "available": True,
        "status": "PAPER_CYCLE_COMPLETED",
        "decision": "NO_ENTRY_SIGNAL",
        "ready_pair_count": 7,
        "reason_codes": {
            "NO_NEW_CROSSOVER": 6,
            "LONG_TREND_INTACT": 1,
            "UNRECOGNIZED_INTERNAL_CODE": 3,
        },
    })

    assert "dane gotowe dla 7/7 par" in text
    assert "brak nowego przecięcia średnich: 6" in text
    assert "trend wzrostowy trwa" in text
    assert "inne warunki bezpieczeństwa: 3" in text
    assert "UNRECOGNIZED_INTERNAL_CODE" not in text


def test_safety_banner_shows_weekly_loss_pause() -> None:
    label, tone, banner = forex_paper_safety_view({
        "status": "READY",
        "loss_streak_safety": {"active": False},
        "weekly_loss_safety": {"active": True},
    })

    assert label == "PAPER — PRZERWA"
    assert tone == "neutral"
    assert "LIMIT TYGODNIOWY" in banner

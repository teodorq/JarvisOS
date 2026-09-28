from __future__ import annotations

from app.trading.forex_risk_diagnostics import build_forex_risk_diagnostics


def _fill(index: int, pnl: object, risk: object | None) -> dict[str, object]:
    return {
        "fill_id": f"close-{index}",
        "action": "CLOSE_LONG",
        "pair": "EUR_USD",
        "realized_pnl_pln": pnl,
        "initial_risk_pln": risk,
    }


def test_risk_diagnostics_calculate_normalized_results() -> None:
    review = build_forex_risk_diagnostics([
        _fill(1, "20.00", "10.00"),
        _fill(2, "-10.00", "10.00"),
        _fill(3, "5.00", "10.00"),
    ])

    assert review["status"] == "COMPLETE"
    assert review["closed_trade_count"] == 3
    assert review["risk_observed_trade_count"] == 3
    assert review["risk_missing_trade_count"] == 0
    assert review["risk_coverage_pct"] == "100.00"
    assert review["net_r_multiple"] == "1.5000"
    assert review["average_r_multiple"] == "0.5000"
    assert review["median_r_multiple"] == "0.5000"
    assert review["best_r_multiple"] == "2.0000"
    assert review["worst_r_multiple"] == "-1.0000"
    assert review["risk_coverage_complete"] is True
    assert review["performance_validated"] is False
    assert review["automatic_strategy_change"] is False
    assert review["live_promotion_ready"] is False


def test_legacy_trade_is_reported_without_inventing_risk() -> None:
    review = build_forex_risk_diagnostics([
        _fill(1, "12.00", None),
        _fill(2, "8.00", "4.00"),
    ])

    assert review["status"] == "PARTIAL"
    assert review["risk_observed_trade_count"] == 1
    assert review["risk_missing_trade_count"] == 1
    assert review["risk_coverage_pct"] == "50.00"
    assert review["average_r_multiple"] == "2.0000"
    assert review["risk_coverage_complete"] is False


def test_invalid_risk_is_missing_and_does_not_create_r_multiple() -> None:
    review = build_forex_risk_diagnostics([
        _fill(1, "10.00", "0"),
        _fill(2, "10.00", "NaN"),
        _fill(3, "NaN", "10.00"),
    ])

    assert review["status"] == "NO_RISK_TELEMETRY"
    assert review["closed_trade_count"] == 3
    assert review["risk_observed_trade_count"] == 0
    assert review["risk_missing_trade_count"] == 3
    assert review["average_r_multiple"] is None


def test_non_closed_or_non_forex_records_are_ignored() -> None:
    review = build_forex_risk_diagnostics([
        None,
        {"action": "OPEN_LONG", "pair": "EUR_USD"},
        {"action": "CLOSE_LONG", "pair": "BTC_USD"},
    ])

    assert review["status"] == "NO_CLOSED_TRADES"
    assert review["closed_trade_count"] == 0
    assert review["risk_coverage_pct"] == "0.00"
    assert review["net_r_multiple"] is None

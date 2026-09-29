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
    assert review["realized_r_recorded_trade_count"] == 0
    assert review["realized_r_derived_trade_count"] == 3
    assert review["realized_r_mismatch_count"] == 0
    assert review["risk_coverage_pct"] == "100.00"
    assert review["net_r_multiple"] == "1.5000"
    assert review["average_r_multiple"] == "0.5000"
    assert review["median_r_multiple"] == "0.5000"
    assert review["best_r_multiple"] == "2.0000"
    assert review["worst_r_multiple"] == "-1.0000"
    assert review["winning_r_trade_count"] == 2
    assert review["losing_r_trade_count"] == 1
    assert review["breakeven_r_trade_count"] == 0
    assert review["maximum_observed_drawdown_r"] == "1.0000"
    assert review["maximum_observed_consecutive_losses"] == 1
    assert review["current_observed_consecutive_losses"] == 0
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
    assert review["maximum_observed_drawdown_r"] is None
    assert review["maximum_observed_consecutive_losses"] == 0


def test_risk_diagnostics_track_observed_drawdown_and_loss_streak() -> None:
    review = build_forex_risk_diagnostics([
        _fill(1, "10", "10"),
        _fill(2, "-5", "10"),
        _fill(3, "-10", "10"),
        _fill(4, "2.5", "10"),
        _fill(5, "-2.5", "10"),
        _fill(6, "-7.5", "10"),
    ])

    assert review["net_r_multiple"] == "-1.2500"
    assert review["maximum_observed_drawdown_r"] == "2.2500"
    assert review["winning_r_trade_count"] == 2
    assert review["losing_r_trade_count"] == 4
    assert review["maximum_observed_consecutive_losses"] == 2
    assert review["current_observed_consecutive_losses"] == 2


def test_recorded_r_is_checked_against_pnl_and_initial_risk() -> None:
    matching = _fill(1, "20", "10")
    matching["realized_r_multiple"] = "2.00004"
    mismatched = _fill(2, "-10", "10")
    mismatched["realized_r_multiple"] = "9.0000"

    review = build_forex_risk_diagnostics([matching, mismatched])

    assert review["risk_observed_trade_count"] == 2
    assert review["realized_r_recorded_trade_count"] == 1
    assert review["realized_r_derived_trade_count"] == 1
    assert review["realized_r_mismatch_count"] == 1
    assert review["net_r_multiple"] == "1.0000"


def test_recorded_r_accepts_only_possible_money_rounding_difference() -> None:
    rounded_legacy = _fill(1, "-8.81", "8.78")
    rounded_legacy["realized_r_multiple"] = "-1.0029"
    outside_rounding = _fill(2, "-8.81", "8.78")
    outside_rounding["realized_r_multiple"] = "-0.9900"

    review = build_forex_risk_diagnostics([rounded_legacy, outside_rounding])

    assert review["realized_r_recorded_trade_count"] == 1
    assert review["realized_r_derived_trade_count"] == 1
    assert review["realized_r_mismatch_count"] == 1


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

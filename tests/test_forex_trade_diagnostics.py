from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.trading.forex_trade_diagnostics import (
    build_forex_trade_diagnostics,
)


UTC = timezone.utc


def _fill(
    index: int,
    *,
    minutes: int | None,
    reason_codes: list[str],
) -> dict[str, object]:
    opened = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    return {
        "fill_id": f"close-{index}",
        "action": "CLOSE_LONG",
        "pair": "EUR_USD",
        "opened_at": opened.isoformat() if minutes is not None else "",
        "closed_at": (
            (opened + timedelta(minutes=minutes)).isoformat()
            if minutes is not None
            else ""
        ),
        "reason_codes": reason_codes,
    }


def test_trade_diagnostics_report_holding_time_and_exit_reasons() -> None:
    review = build_forex_trade_diagnostics([
        _fill(1, minutes=30, reason_codes=["STOP_LOSS_TRIGGERED"]),
        _fill(2, minutes=60, reason_codes=["TAKE_PROFIT_TRIGGERED"]),
        _fill(3, minutes=90, reason_codes=["SMA_DIRECTION_CHANGED"]),
        _fill(4, minutes=None, reason_codes=[]),
    ])

    assert review["status"] == "INCOMPLETE"
    assert review["closed_trade_count"] == 4
    assert review["holding_time_observed_count"] == 3
    assert review["holding_time_missing_count"] == 1
    assert review["average_holding_minutes"] == "60.00"
    assert review["median_holding_minutes"] == "60.00"
    assert review["shortest_holding_minutes"] == "30.00"
    assert review["longest_holding_minutes"] == "90.00"
    assert review["exit_reason_counts"] == {
        "stop_loss": 1,
        "take_profit": 1,
        "strategy": 1,
        "unspecified": 1,
    }
    assert review["diagnostics_complete"] is False
    assert review["automatic_strategy_change"] is False
    assert review["live_promotion_ready"] is False


def test_empty_diagnostics_do_not_claim_performance_validation() -> None:
    review = build_forex_trade_diagnostics([])

    assert review["status"] == "NO_CLOSED_TRADES"
    assert review["closed_trade_count"] == 0
    assert review["average_holding_minutes"] is None
    assert review["performance_validated"] is False
    assert review["live_promotion_ready"] is False


def test_invalid_or_non_forex_records_are_ignored() -> None:
    review = build_forex_trade_diagnostics([
        None,
        {"action": "OPEN_LONG", "pair": "EUR_USD"},
        {"action": "CLOSE_LONG", "pair": "BTC_USD"},
    ])

    assert review["closed_trade_count"] == 0

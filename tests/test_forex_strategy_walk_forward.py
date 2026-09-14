from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.trading.forex_models import HISTORICAL_FOREX_PAIRS
from app.trading.forex_portfolio_historical import (
    ForexPortfolioHistoricalPolicy,
    ForexPortfolioHistoricalWalkForwardValidator,
    ForexPortfolioWalkForwardPolicy,
)
from app.trading.forex_strategy_walk_forward import (
    ForexStrategyCounterfactualWalkForwardComparison,
)
from app.trading.models import MarketBar, TradingValidationError


def _histories(count: int = 251) -> dict[str, tuple[MarketBar, ...]]:
    started = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    bases = {
        "EUR_USD": Decimal("1.1000"),
        "GBP_USD": Decimal("1.2800"),
        "USD_JPY": Decimal("145.00"),
        "USD_CHF": Decimal("0.8800"),
        "AUD_USD": Decimal("0.6600"),
        "USD_CAD": Decimal("1.3500"),
        "NZD_USD": Decimal("0.6100"),
        "USD_PLN": Decimal("4.0000"),
    }
    result: dict[str, tuple[MarketBar, ...]] = {}
    for pair in HISTORICAL_FOREX_PAIRS:
        price = bases[pair.symbol]
        bars = []
        for index in range(count):
            if pair.symbol == "USD_PLN":
                change = Decimal("0")
            else:
                direction = Decimal("1") if (index // 10) % 2 else Decimal("-1")
                change = pair.pip_size * Decimal("12") * direction
            opened = price
            closed = price + change
            wick = pair.pip_size * Decimal("3")
            bars.append(MarketBar.create(
                symbol=pair.symbol,
                timestamp=started + timedelta(minutes=15 * index),
                open=opened,
                high=max(opened, closed) + wick,
                low=min(opened, closed) - wick,
                close=closed,
                volume="100",
                currency=pair.quote_currency,
            ))
            price = closed
        result[pair.symbol] = tuple(bars)
    return result


def _comparison() -> ForexStrategyCounterfactualWalkForwardComparison:
    return ForexStrategyCounterfactualWalkForwardComparison(
        walk_forward_policy=ForexPortfolioWalkForwardPolicy(
            training_bar_count=211,
            testing_bar_count=20,
            step_bar_count=20,
            minimum_trade_count=1,
            minimum_profitable_window_ratio=Decimal("0.50"),
        )
    )


def test_comparison_freezes_one_shot_histories_and_is_auditable() -> None:
    one_shot = {
        symbol: (bar for bar in bars)
        for symbol, bars in _histories().items()
    }

    result = _comparison().run(one_shot)

    assert result["status"] == "FOREX_COUNTERFACTUAL_WALK_FORWARD_COMPLETED"
    assert result["account_currency"] == "PLN"
    assert result["window_count"] == 2
    assert result["identical_source_data"] is True
    assert result["identical_execution_policy"] is True
    assert result["identical_window_policy"] is True
    assert result["identical_out_of_sample_windows"] is True
    assert result["portfolio_states_isolated"] is True
    assert result["closed_m15_bars_required"] is True
    assert result["future_bar_access"] is False
    assert result["performance_validated"] is False
    assert result["automatic_paper_strategy_change"] is False
    assert result["paper_orders_sent"] is False
    assert result["live_orders_sent"] is False
    assert result["real_money_access"] is False
    assert len(result["manifest"]["data_sha256"]) == 64
    assert len(result["manifest"]["implementation_sha256"]) == 64
    assert (
        result["manifest"]["implementation_fingerprint_kind"]
        == "NORMALIZED_PYTHON_SOURCE_SHA256"
    )
    assert len(result["manifest"]["execution_policy_sha256"]) == 64
    assert len(result["manifest"]["window_policy_sha256"]) == 64
    assert len(result["manifest"]["v1_policy_sha256"]) == 64
    assert len(result["manifest"]["v2_policy_sha256"]) == 64
    assert len(result["manifest"]["comparison_contract_sha256"]) == 64
    assert result["manifest"]["v2_candidate_id"] == "FOREX_REGIME_V2_20260820"
    assert result["manifest"]["v2_frozen_after"].startswith("2026-08-20T")
    assert result["baseline_v1"] is not result["candidate_v2"]
    assert (
        result["aggregate"]["v2_higher_return_window_count"]
        + result["aggregate"]["equal_return_window_count"]
        + result["aggregate"]["v2_lower_return_window_count"]
        == result["window_count"]
    )
    assert result["aggregate"]["winner_selected"] is False
    for window in result["windows"]:
        assert "delta_v2_minus_v1" in window
        assert window["v1"] is not window["v2"]


def test_comparison_is_deterministic_and_future_bars_do_not_change_old_windows() -> None:
    comparison = _comparison()
    shorter = comparison.run(_histories(251))
    longer = comparison.run(_histories(271))

    assert shorter == comparison.run(_histories(251))
    assert shorter["windows"] == longer["windows"][:2]
    assert shorter["manifest"]["data_sha256"] != longer["manifest"]["data_sha256"]
    assert (
        shorter["manifest"]["execution_policy_sha256"]
        == longer["manifest"]["execution_policy_sha256"]
    )


def test_comparison_requires_full_v2_warmup_and_matching_scanner_policy() -> None:
    with pytest.raises(TradingValidationError, match="insufficient_v2_warmup"):
        ForexStrategyCounterfactualWalkForwardComparison(
            walk_forward_policy=ForexPortfolioWalkForwardPolicy(
                training_bar_count=210,
                testing_bar_count=20,
                step_bar_count=20,
            )
        )

    from app.trading.forex_scanner import ForexScannerPolicy

    with pytest.raises(TradingValidationError, match="scanner_policy_mismatch"):
        ForexStrategyCounterfactualWalkForwardComparison(
            ForexPortfolioHistoricalPolicy(
                scanner=ForexScannerPolicy(fast_window=9, slow_window=30)
            )
        )


def test_comparison_fails_closed_when_window_boundaries_diverge() -> None:
    real_run = ForexPortfolioHistoricalWalkForwardValidator.run
    calls = 0

    def divergent_run(self, values):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        result = real_run(self, values)
        if calls == 2:
            result = deepcopy(result)
            result["windows"][0]["testing_start_at"] = (
                datetime.fromisoformat(result["windows"][0]["testing_start_at"])
                + timedelta(minutes=15)
            ).isoformat()
        return result

    with patch.object(
        ForexPortfolioHistoricalWalkForwardValidator,
        "run",
        divergent_run,
    ):
        with pytest.raises(
            TradingValidationError,
            match="window_boundaries_mismatch",
        ):
            _comparison().run(_histories(231))


def test_comparison_rejects_broken_m15_cadence() -> None:
    histories = _histories(231)
    broken = list(histories["EUR_USD"])
    item = broken[220]
    broken[220] = MarketBar.create(
        symbol=item.symbol,
        timestamp=item.timestamp + timedelta(minutes=1),
        open=item.open,
        high=item.high,
        low=item.low,
        close=item.close,
        volume=item.volume,
        currency=item.currency,
    )
    histories["EUR_USD"] = tuple(broken)

    with pytest.raises(TradingValidationError, match="invalid_m15_cadence"):
        _comparison().run(histories)

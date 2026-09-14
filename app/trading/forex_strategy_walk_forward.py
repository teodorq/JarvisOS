"""Auditable walk-forward comparison of frozen Forex PAPER strategies."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

from app.trading.forex_candidate_v2 import ForexRegimeFilteredScanner
from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_models import ForexBar
from app.trading.forex_portfolio_historical import (
    ForexPortfolioHistoricalPolicy,
    ForexPortfolioHistoricalWalkForwardValidator,
    ForexPortfolioWalkForwardPolicy,
)
from app.trading.forex_scanner import ForexMarketScanner
from app.trading.forex_risk import ForexPaperPolicy, ForexRateBook
from app.trading.models import MarketBar, TradingValidationError


_PERCENT = Decimal("0.0001")
_MONEY = Decimal("0.01")
_WINDOW_BOUNDARY_FIELDS = (
    "training_start_at",
    "training_end_at",
    "testing_start_at",
    "testing_end_at",
)


def _decimal_text(value: Decimal, quantum: Decimal = _PERCENT) -> str:
    return str(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _canonical(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def _sha256(value: object) -> str:
    encoded = json.dumps(
        _canonical(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ForexStrategyCounterfactualWalkForwardComparison:
    """Compare V1 and frozen V2 on identical isolated PLN portfolios."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        historical_policy: ForexPortfolioHistoricalPolicy | None = None,
        *,
        walk_forward_policy: ForexPortfolioWalkForwardPolicy | None = None,
    ) -> None:
        self.historical_policy = (
            historical_policy or ForexPortfolioHistoricalPolicy()
        )
        self.walk_forward_policy = (
            walk_forward_policy or ForexPortfolioWalkForwardPolicy()
        )
        self.candidate_scanner = ForexRegimeFilteredScanner()
        if self.candidate_scanner.policy != self.historical_policy.scanner:
            raise TradingValidationError(
                "forex_strategy_walk_forward: scanner_policy_mismatch"
            )
        if (
            self.walk_forward_policy.training_bar_count
            < self.candidate_scanner.required_history_count
        ):
            raise TradingValidationError(
                "forex_strategy_walk_forward: insufficient_v2_warmup"
            )

    def run(
        self,
        values: Mapping[str, Iterable[MarketBar]],
    ) -> dict[str, Any]:
        histories = self._freeze_histories(values)
        self._validate_m15_cadence(histories)
        baseline = ForexPortfolioHistoricalWalkForwardValidator(
            historical_policy=self.historical_policy,
            walk_forward_policy=self.walk_forward_policy,
            scanner=ForexMarketScanner(policy=self.historical_policy.scanner),
        ).run(histories)
        candidate = ForexPortfolioHistoricalWalkForwardValidator(
            historical_policy=self.historical_policy,
            walk_forward_policy=self.walk_forward_policy,
            scanner=self.candidate_scanner,
        ).run(histories)
        self._validate_results(baseline, candidate)
        comparisons = self._window_comparisons(baseline, candidate)
        manifest = self._manifest(histories)
        aggregate = self._aggregate(baseline, candidate, comparisons)
        return {
            "status": "FOREX_COUNTERFACTUAL_WALK_FORWARD_COMPLETED",
            "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
            "schema_version": self.SCHEMA_VERSION,
            "account_currency": "PLN",
            "manifest": manifest,
            "window_count": len(comparisons),
            "windows": comparisons,
            "aggregate": aggregate,
            "baseline_v1": baseline,
            "candidate_v2": candidate,
            "identical_source_data": True,
            "identical_execution_policy": True,
            "identical_window_policy": True,
            "identical_out_of_sample_windows": True,
            "portfolio_states_isolated": True,
            "closed_m15_bars_required": True,
            "m15_cadence_validated": True,
            "past_only_warmup_used": True,
            "same_bar_signal_execution_blocked": True,
            "future_bar_access": False,
            "parameter_optimization_performed": False,
            "reused_historical_source_data": True,
            "forward_validation_required": True,
            "performance_validated": False,
            "automatic_paper_strategy_change": False,
            "broker_connection_used": False,
            "network_access": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    @staticmethod
    def _freeze_histories(
        values: Mapping[str, Iterable[MarketBar]],
    ) -> dict[str, tuple[MarketBar, ...]]:
        if not isinstance(values, Mapping):
            raise TradingValidationError(
                "forex_strategy_walk_forward: histories_mapping_required"
            )
        return {str(symbol): tuple(bars) for symbol, bars in values.items()}

    @staticmethod
    def _validate_m15_cadence(
        histories: Mapping[str, tuple[MarketBar, ...]],
    ) -> None:
        for bars in histories.values():
            for bar in bars:
                stamp = getattr(bar, "timestamp", None)
                if (
                    not isinstance(bar, MarketBar)
                    or not isinstance(stamp, datetime)
                    or stamp.second != 0
                    or stamp.microsecond != 0
                    or stamp.minute not in {0, 15, 30, 45}
                ):
                    raise TradingValidationError(
                        "forex_strategy_walk_forward: invalid_m15_cadence"
                    )
            for left, right in zip(bars, bars[1:]):
                seconds = int((right.timestamp - left.timestamp).total_seconds())
                if seconds == 900:
                    continue
                weekend = (
                    left.timestamp.weekday() == 4
                    and right.timestamp.weekday() in {6, 0}
                    and 24 * 3600 <= seconds <= 80 * 3600
                    and seconds % 900 == 0
                )
                if not weekend:
                    raise TradingValidationError(
                        "forex_strategy_walk_forward: invalid_m15_cadence"
                    )

    @staticmethod
    def _validate_results(
        baseline: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> None:
        if baseline.get("account_currency") != "PLN" or candidate.get(
            "account_currency"
        ) != "PLN":
            raise TradingValidationError(
                "forex_strategy_walk_forward: account_currency_mismatch"
            )
        baseline_windows = tuple(baseline.get("windows", ()))
        candidate_windows = tuple(candidate.get("windows", ()))
        if len(baseline_windows) != len(candidate_windows) or not baseline_windows:
            raise TradingValidationError(
                "forex_strategy_walk_forward: window_count_mismatch"
            )
        for baseline_window, candidate_window in zip(
            baseline_windows, candidate_windows
        ):
            if baseline_window.get("window") != candidate_window.get("window"):
                raise TradingValidationError(
                    "forex_strategy_walk_forward: window_identity_mismatch"
                )
            if any(
                baseline_window.get(field) != candidate_window.get(field)
                for field in _WINDOW_BOUNDARY_FIELDS
            ):
                raise TradingValidationError(
                    "forex_strategy_walk_forward: window_boundaries_mismatch"
                )
            baseline_test = baseline_window.get("testing", {})
            candidate_test = candidate_window.get("testing", {})
            if (
                baseline_test.get("initial_equity_pln")
                != candidate_test.get("initial_equity_pln")
            ):
                raise TradingValidationError(
                    "forex_strategy_walk_forward: execution_policy_mismatch"
                )
        required_true = (
            "chronological_splits_valid",
            "out_of_sample_windows_non_overlapping",
            "past_only_warmup_used",
            "same_bar_signal_execution_blocked",
            "portfolio_pln_aggregation_performed",
            "historical_pln_conversion_series_verified",
        )
        if any(
            result.get(field) is not True
            for result in (baseline, candidate)
            for field in required_true
        ):
            raise TradingValidationError(
                "forex_strategy_walk_forward: unsafe_result_contract"
            )
        required_false = (
            "automatic_paper_promotion",
            "broker_connection_used",
            "paper_orders_sent",
            "live_orders_sent",
        )
        if any(
            result.get(field) is not False
            for result in (baseline, candidate)
            for field in required_false
        ):
            raise TradingValidationError(
                "forex_strategy_walk_forward: unsafe_execution_state"
            )
        if baseline.get("scanner_matches_paper") is not True or candidate.get(
            "scanner_matches_paper"
        ) is not False:
            raise TradingValidationError(
                "forex_strategy_walk_forward: strategy_identity_mismatch"
            )

    @classmethod
    def _window_comparisons(
        cls,
        baseline: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for baseline_window, candidate_window in zip(
            baseline["windows"], candidate["windows"]
        ):
            baseline_test = baseline_window["testing"]
            candidate_test = candidate_window["testing"]
            v1 = cls._testing_summary(baseline_test)
            v2 = cls._testing_summary(candidate_test)
            result.append({
                "window": baseline_window["window"],
                **{
                    field: baseline_window[field]
                    for field in _WINDOW_BOUNDARY_FIELDS
                },
                "v1": v1,
                "v2": v2,
                "delta_v2_minus_v1": {
                    "return_pct": _decimal_text(
                        Decimal(v2["return_pct"]) - Decimal(v1["return_pct"])
                    ),
                    "maximum_drawdown_pct": _decimal_text(
                        Decimal(v2["maximum_drawdown_pct"])
                        - Decimal(v1["maximum_drawdown_pct"])
                    ),
                    "ending_equity_pln": _decimal_text(
                        Decimal(v2["ending_equity_pln"])
                        - Decimal(v1["ending_equity_pln"]),
                        _MONEY,
                    ),
                    "trade_count": v2["trade_count"] - v1["trade_count"],
                    "profitable_trade_count": (
                        v2["profitable_trade_count"]
                        - v1["profitable_trade_count"]
                    ),
                    "stop_loss_exit_count": (
                        v2["stop_loss_exit_count"]
                        - v1["stop_loss_exit_count"]
                    ),
                    "take_profit_exit_count": (
                        v2["take_profit_exit_count"]
                        - v1["take_profit_exit_count"]
                    ),
                    "rejected_candidate_count": (
                        v2["rejected_candidate_count"]
                        - v1["rejected_candidate_count"]
                    ),
                },
            })
        return result

    @staticmethod
    def _testing_summary(value: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "return_pct": str(value["return_pct"]),
            "maximum_drawdown_pct": str(value["maximum_drawdown_pct"]),
            "ending_equity_pln": str(value["ending_equity_pln"]),
            "trade_count": int(value["trade_count"]),
            "profitable_trade_count": int(value["profitable_trade_count"]),
            "stop_loss_exit_count": int(value["stop_loss_exit_count"]),
            "take_profit_exit_count": int(value["take_profit_exit_count"]),
            "ambiguous_bar_count": int(value["ambiguous_bar_count"]),
            "rejected_candidate_count": int(value["rejected_candidate_count"]),
        }

    @classmethod
    def _aggregate(
        cls,
        baseline: Mapping[str, Any],
        candidate: Mapping[str, Any],
        windows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        v1 = cls._portfolio_summary(baseline)
        v2 = cls._portfolio_summary(candidate)
        relations = [
            Decimal(window["v2"]["return_pct"])
            .compare(Decimal(window["v1"]["return_pct"]))
            for window in windows
        ]
        return {
            "v1": v1,
            "v2": v2,
            "delta_v2_minus_v1": {
                "average_out_of_sample_return_pct": _decimal_text(
                    Decimal(v2["average_out_of_sample_return_pct"])
                    - Decimal(v1["average_out_of_sample_return_pct"])
                ),
                "compounded_out_of_sample_return_pct": _decimal_text(
                    Decimal(v2["compounded_out_of_sample_return_pct"])
                    - Decimal(v1["compounded_out_of_sample_return_pct"])
                ),
                "maximum_out_of_sample_drawdown_pct": _decimal_text(
                    Decimal(v2["maximum_out_of_sample_drawdown_pct"])
                    - Decimal(v1["maximum_out_of_sample_drawdown_pct"])
                ),
                "out_of_sample_trade_count": (
                    v2["out_of_sample_trade_count"]
                    - v1["out_of_sample_trade_count"]
                ),
                "profitable_out_of_sample_window_count": (
                    v2["profitable_out_of_sample_window_count"]
                    - v1["profitable_out_of_sample_window_count"]
                ),
            },
            "v2_higher_return_window_count": sum(value > 0 for value in relations),
            "equal_return_window_count": sum(value == 0 for value in relations),
            "v2_lower_return_window_count": sum(value < 0 for value in relations),
            "winner_selected": False,
            "strategy_recommendation_generated": False,
        }

    @staticmethod
    def _portfolio_summary(value: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "average_out_of_sample_return_pct": str(
                value["average_out_of_sample_return_pct"]
            ),
            "compounded_out_of_sample_return_pct": str(
                value["compounded_out_of_sample_return_pct"]
            ),
            "maximum_out_of_sample_drawdown_pct": str(
                value["maximum_out_of_sample_drawdown_pct"]
            ),
            "out_of_sample_trade_count": int(value["out_of_sample_trade_count"]),
            "profitable_out_of_sample_window_count": int(
                value["profitable_out_of_sample_window_count"]
            ),
            "out_of_sample_stop_loss_exit_count": int(
                value["out_of_sample_stop_loss_exit_count"]
            ),
            "out_of_sample_take_profit_exit_count": int(
                value["out_of_sample_take_profit_exit_count"]
            ),
            "out_of_sample_ambiguous_bar_count": int(
                value["out_of_sample_ambiguous_bar_count"]
            ),
        }

    def _manifest(
        self,
        histories: Mapping[str, tuple[MarketBar, ...]],
    ) -> dict[str, Any]:
        execution_policy = asdict(self.historical_policy)
        window_policy = asdict(self.walk_forward_policy)
        v1_policy = {
            "strategy": "PAPER_BASE_SCANNER",
            "scanner": asdict(self.historical_policy.scanner),
        }
        candidate = self.candidate_scanner.candidate_policy
        core = {
            "schema_version": self.SCHEMA_VERSION,
            "data_sha256": self._data_sha256(histories),
            "implementation_sha256": self._implementation_sha256(),
            "implementation_fingerprint_kind": "NORMALIZED_PYTHON_SOURCE_SHA256",
            "execution_policy_sha256": _sha256(execution_policy),
            "window_policy_sha256": _sha256(window_policy),
            "v1_policy_sha256": _sha256(v1_policy),
            "v2_candidate_id": candidate.candidate_id,
            "v2_frozen_after": candidate.frozen_after.isoformat(),
            "v2_policy_sha256": candidate.fingerprint_sha256,
        }
        return {
            **core,
            "comparison_contract_sha256": _sha256(core),
            "pair_count": len(histories),
            "bar_count_per_pair": (
                len(next(iter(histories.values()))) if histories else 0
            ),
            "initial_equity_pln": str(
                self.historical_policy.initial_equity_pln
            ),
            "assumed_spread_pips": str(
                self.historical_policy.assumed_spread_pips
            ),
            "assumed_slippage_pips": str(
                self.historical_policy.assumed_slippage_pips
            ),
            "training_bar_count": self.walk_forward_policy.training_bar_count,
            "testing_bar_count": self.walk_forward_policy.testing_bar_count,
            "step_bar_count": self.walk_forward_policy.step_bar_count,
        }

    @staticmethod
    def _data_sha256(
        histories: Mapping[str, tuple[MarketBar, ...]],
    ) -> str:
        digest = hashlib.sha256()
        for symbol in sorted(histories):
            for bar in histories[symbol]:
                row = {
                    "symbol": bar.symbol,
                    "timestamp": bar.timestamp.isoformat(),
                    "open": str(bar.open),
                    "high": str(bar.high),
                    "low": str(bar.low),
                    "close": str(bar.close),
                    "volume": str(bar.volume),
                    "currency": bar.currency,
                }
                digest.update(
                    json.dumps(
                        row,
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                digest.update(b"\n")
        return digest.hexdigest()

    @classmethod
    def _implementation_sha256(cls) -> str:
        classes = (
            cls,
            ForexPortfolioHistoricalWalkForwardValidator,
            ForexRegimeFilteredScanner,
            ForexMarketScanner,
            ForexPaperCoordinator,
            ForexPaperPolicy,
            ForexRateBook,
            ForexBar,
            MarketBar,
        )
        module_names = sorted({item.__module__ for item in classes})
        digest = hashlib.sha256()
        for module_name in module_names:
            module = sys.modules.get(module_name)
            raw_path = getattr(module, "__file__", None)
            if not raw_path:
                raise TradingValidationError(
                    "forex_strategy_walk_forward: implementation_source_unavailable"
                )
            try:
                source = Path(raw_path).read_bytes().replace(b"\r\n", b"\n")
            except OSError as error:
                raise TradingValidationError(
                    "forex_strategy_walk_forward: implementation_source_unavailable"
                ) from error
            digest.update(module_name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source)
            digest.update(b"\0")
        return digest.hexdigest()


__all__ = ["ForexStrategyCounterfactualWalkForwardComparison"]

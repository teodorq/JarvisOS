"""Run fixed, local walk-forward research on the latest verified MT5 export."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.market_data.mt5_history import Mt5DemoHistoricalExporter  # noqa: E402
from app.trading.dataset import HistoricalCsvLoader  # noqa: E402
from app.trading.forex_historical import (  # noqa: E402
    ForexHistoricalWalkForwardValidator,
    ForexWalkForwardPolicy,
)
from app.trading.forex_models import MAJOR_FOREX_PAIRS  # noqa: E402
from app.trading.forex_candidate_v2 import ForexRegimeFilteredScanner  # noqa: E402
from app.trading.forex_portfolio_historical import (  # noqa: E402
    ForexPortfolioHistoricalWalkForwardValidator,
    ForexPortfolioWalkForwardPolicy,
)
from app.trading.models import TradingValidationError  # noqa: E402


def _write_report(report: dict[str, object]) -> Path:
    target = PROJECT_ROOT / "data" / "trading" / "research" / "latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".forex-research-",
        suffix=".json",
        dir=target.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="JARVIS OS: lokalny walk-forward Forex LONG/SHORT bez zleceń.",
    )
    parser.add_argument("--training-bars", type=int, default=1_500)
    parser.add_argument("--testing-bars", type=int, default=500)
    parser.add_argument("--step-bars", type=int, default=500)
    arguments = parser.parse_args()
    try:
        verified = Mt5DemoHistoricalExporter(PROJECT_ROOT).verify_latest()
        if verified.get("research_quality_ready") is not True:
            raise TradingValidationError("forex_research: history_quality_not_ready")
        if verified.get("historical_pln_conversion_ready") is not True:
            raise TradingValidationError(
                "forex_research: historical_pln_conversion_not_ready"
            )
        export_path = Path(str(verified["export_path"]))
        window_policy = ForexWalkForwardPolicy(
            training_bar_count=arguments.training_bars,
            testing_bar_count=arguments.testing_bars,
            step_bar_count=arguments.step_bars,
        )
        validator = ForexHistoricalWalkForwardValidator(
            walk_forward_policy=window_policy,
        )
        loader = HistoricalCsvLoader()
        major_symbols = frozenset(pair.symbol for pair in MAJOR_FOREX_PAIRS)
        histories = {}
        pair_results = []
        for raw in verified["datasets"]:
            pair = str(raw["pair"])
            dataset = loader.load(export_path / f"{pair.lower()}_m15.csv")
            histories[pair] = dataset.bars
            if pair not in major_symbols:
                continue
            result = validator.run(dataset.bars)
            pair_results.append({
                "pair": pair,
                "quote_currency": result["quote_currency"],
                "window_count": result["window_count"],
                "out_of_sample_trade_count": result["out_of_sample_trade_count"],
                "out_of_sample_stop_loss_exit_count": result[
                    "out_of_sample_stop_loss_exit_count"
                ],
                "out_of_sample_take_profit_exit_count": result[
                    "out_of_sample_take_profit_exit_count"
                ],
                "out_of_sample_ambiguous_bar_count": result[
                    "out_of_sample_ambiguous_bar_count"
                ],
                "profitable_out_of_sample_window_count": result[
                    "profitable_out_of_sample_window_count"
                ],
                "average_out_of_sample_return_pct": result[
                    "average_out_of_sample_return_pct"
                ],
                "compounded_out_of_sample_return_pct": result[
                    "compounded_out_of_sample_return_pct"
                ],
                "maximum_out_of_sample_drawdown_pct": result[
                    "maximum_out_of_sample_drawdown_pct"
                ],
                "details": result,
            })
        positive_pairs = [
            str(item["pair"])
            for item in pair_results
            if Decimal(str(item["average_out_of_sample_return_pct"])) > 0
        ]
        non_positive_pairs = [
            str(item["pair"])
            for item in pair_results
            if Decimal(str(item["average_out_of_sample_return_pct"])) <= 0
        ]
        portfolio = ForexPortfolioHistoricalWalkForwardValidator(
            walk_forward_policy=ForexPortfolioWalkForwardPolicy(
                training_bar_count=arguments.training_bars,
                testing_bar_count=arguments.testing_bars,
                step_bar_count=arguments.step_bars,
            ),
        ).run(histories)
        candidate_scanner = ForexRegimeFilteredScanner()
        candidate_portfolio = ForexPortfolioHistoricalWalkForwardValidator(
            walk_forward_policy=ForexPortfolioWalkForwardPolicy(
                training_bar_count=arguments.training_bars,
                testing_bar_count=arguments.testing_bars,
                step_bar_count=arguments.step_bars,
            ),
            scanner=candidate_scanner,
        ).run(histories)
        candidate_historical_checks_passed = bool(
            candidate_portfolio["strategy_performance_validated"]
        )
        candidate_portfolio["historical_development_checks_passed"] = (
            candidate_historical_checks_passed
        )
        candidate_portfolio["reused_source_data"] = True
        candidate_portfolio["forward_validation_required"] = True
        candidate_portfolio["strategy_performance_validated"] = False
        candidate_portfolio["automatic_paper_promotion"] = False
        candidate_portfolio["paper_orders_sent"] = False
        candidate_portfolio["live_orders_sent"] = False
        development_candidate_v2 = {
            "status": "DEVELOPMENT_REPLAY_COMPLETED",
            "candidate_id": candidate_scanner.candidate_policy.candidate_id,
            "policy_fingerprint_sha256": (
                candidate_scanner.candidate_policy.fingerprint_sha256
            ),
            "frozen_after": (
                candidate_scanner.candidate_policy.frozen_after.isoformat()
            ),
            "reused_source_data": True,
            "historical_development_checks_passed": (
                candidate_historical_checks_passed
            ),
            "forward_validation_required": True,
            "strategy_performance_validated": False,
            "strategy_candidate_ready": False,
            "strategy_candidate_blocks": ["FORWARD_OBSERVATION_REQUIRED"],
            "portfolio": candidate_portfolio,
            "automatic_paper_promotion": False,
            "broker_connection_used": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }
        block_by_check = {
            "average_return_positive": "PORTFOLIO_AVERAGE_RETURN_NOT_POSITIVE",
            "compounded_return_positive": "PORTFOLIO_COMPOUNDED_RETURN_NOT_POSITIVE",
            "profitable_window_ratio_met": "PORTFOLIO_PROFITABLE_WINDOW_RATIO_NOT_MET",
            "maximum_drawdown_within_limit": "PORTFOLIO_DRAWDOWN_LIMIT_EXCEEDED",
            "minimum_trade_count_met": "PORTFOLIO_MINIMUM_TRADE_COUNT_NOT_MET",
        }
        candidate_blocks = [
            block_by_check[key]
            for key, passed in portfolio["performance_checks"].items()
            if passed is not True
        ]
        candidate_ready = not candidate_blocks
        report: dict[str, object] = {
            "status": "FOREX_MULTI_PAIR_RESEARCH_COMPLETED",
            "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_export_id": verified["export_id"],
            "source_fingerprints_verified": True,
            "source_quality_ready": True,
            "pair_count": len(pair_results),
            "pairs": pair_results,
            "positive_average_pair_count": len(positive_pairs),
            "positive_average_pairs": positive_pairs,
            "non_positive_average_pairs": non_positive_pairs,
            "strategy_candidate_ready": candidate_ready,
            "strategy_candidate_blocks": candidate_blocks,
            "portfolio": portfolio,
            "development_candidate_v2": development_candidate_v2,
            "portfolio_pln_aggregation_performed": True,
            "historical_pln_conversion_series_verified": True,
            "result_currency_note": (
                "Individual pair results are diagnostic. Candidate readiness is "
                "decided only by the aligned, multi-pair PLN portfolio replay."
            ),
            "parameter_optimization_performed": False,
            "stop_loss_formula_matches_paper_coordinator": True,
            "position_sizing_matches_paper_coordinator": True,
            "take_profit_research_only": False,
            "take_profit_matches_paper": True,
            "ambiguous_stop_target_bar_uses_stop_first": True,
            "strategy_performance_validated": portfolio[
                "strategy_performance_validated"
            ],
            "automatic_paper_promotion": False,
            "broker_connection_used": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }
        report_path = _write_report(report)
        summary = {
            "status": report["status"],
            "mode": report["mode"],
            "source_export_id": report["source_export_id"],
            "source_fingerprints_verified": True,
            "source_quality_ready": True,
            "pair_count": len(pair_results),
            "pairs": [
                {key: value for key, value in item.items() if key != "details"}
                for item in pair_results
            ],
            "positive_average_pair_count": len(positive_pairs),
            "positive_average_pairs": positive_pairs,
            "non_positive_average_pairs": non_positive_pairs,
            "strategy_candidate_ready": candidate_ready,
            "strategy_candidate_blocks": candidate_blocks,
            "report_path": str(report_path),
            "portfolio_pln_aggregation_performed": True,
            "historical_pln_conversion_series_verified": True,
            "portfolio": {
                key: value
                for key, value in portfolio.items()
                if key != "windows"
            },
            "development_candidate_v2": {
                **{
                    key: value
                    for key, value in development_candidate_v2.items()
                    if key != "portfolio"
                },
                "portfolio": {
                    key: value
                    for key, value in candidate_portfolio.items()
                    if key != "windows"
                },
            },
            "parameter_optimization_performed": False,
            "stop_loss_formula_matches_paper_coordinator": True,
            "position_sizing_matches_paper_coordinator": True,
            "take_profit_research_only": False,
            "take_profit_matches_paper": True,
            "ambiguous_stop_target_bar_uses_stop_first": True,
            "strategy_performance_validated": portfolio[
                "strategy_performance_validated"
            ],
            "automatic_paper_promotion": False,
            "broker_connection_used": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }
    except (OSError, ValueError, TradingValidationError) as error:
        print(json.dumps({
            "status": "BLOCKED",
            "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
            "reason": str(error)[:200],
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

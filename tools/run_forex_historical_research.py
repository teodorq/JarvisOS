"""Run fixed, local walk-forward research on the latest verified MT5 export."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
        pair_results = []
        for raw in verified["datasets"]:
            pair = str(raw["pair"])
            dataset = loader.load(export_path / f"{pair.lower()}_m15.csv")
            result = validator.run(dataset.bars)
            pair_results.append({
                "pair": pair,
                "quote_currency": result["quote_currency"],
                "window_count": result["window_count"],
                "out_of_sample_trade_count": result["out_of_sample_trade_count"],
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
        report: dict[str, object] = {
            "status": "FOREX_MULTI_PAIR_RESEARCH_COMPLETED",
            "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_export_id": verified["export_id"],
            "source_fingerprints_verified": True,
            "source_quality_ready": True,
            "pair_count": len(pair_results),
            "pairs": pair_results,
            "portfolio_pln_aggregation_performed": False,
            "result_currency_note": (
                "Each pair is reported in its own quote currency; results are not "
                "summed into a PLN portfolio without historical conversion rates."
            ),
            "parameter_optimization_performed": False,
            "strategy_performance_validated": False,
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
            "report_path": str(report_path),
            "portfolio_pln_aggregation_performed": False,
            "parameter_optimization_performed": False,
            "strategy_performance_validated": False,
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

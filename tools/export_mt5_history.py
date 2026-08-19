"""Export closed M15 history from the local MT5 DEMO terminal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.market_data.forex_environment import (  # noqa: E402
    ForexDataSettings,
    load_forex_environment,
)
from app.market_data.mt5_demo import Mt5DemoReadOnlySource  # noqa: E402
from app.market_data.mt5_history import Mt5DemoHistoricalExporter  # noqa: E402
from app.trading.forex_models import MAJOR_FOREX_PAIRS, major_pair  # noqa: E402
from app.trading.models import TradingValidationError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "JARVIS OS: lokalny eksport zamkniętych świec M15 z MT5 DEMO."
        )
    )
    parser.add_argument("--bars", type=int, default=5_000)
    parser.add_argument("--verify-latest", action="store_true")
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        help="Para główna, np. EUR_USD. Bez tej opcji eksportuje wszystkie 7.",
    )
    arguments = parser.parse_args()
    try:
        if arguments.verify_latest:
            result = Mt5DemoHistoricalExporter(PROJECT_ROOT).verify_latest()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        load_forex_environment(PROJECT_ROOT)
        settings = ForexDataSettings.from_environment()
        if not settings.enabled or settings.primary_provider != "MT5_DEMO":
            raise TradingValidationError("mt5_history: mt5_demo_not_enabled")
        pairs = (
            tuple(major_pair(value) for value in arguments.pair)
            if arguments.pair
            else MAJOR_FOREX_PAIRS
        )
        exporter = Mt5DemoHistoricalExporter(
            PROJECT_ROOT,
            source=Mt5DemoReadOnlySource(
                symbol_suffix=settings.mt5_symbol_suffix,
            ),
        )
        result = exporter.export(pairs, bar_count=arguments.bars)
    except (TradingValidationError, ValueError) as error:
        print(json.dumps({
            "status": "BLOCKED",
            "mode": "READ_ONLY_HISTORICAL_RESEARCH",
            "reason": str(error)[:160],
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

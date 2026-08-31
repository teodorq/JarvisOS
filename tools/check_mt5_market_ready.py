"""Probe local MT5 DEMO market freshness without any order capability."""

from __future__ import annotations

from datetime import datetime, timezone
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
from app.market_data.mt5_demo import (  # noqa: E402
    Mt5DemoReadOnlySource,
    mt5_market_snapshot_fresh,
)
from app.trading.forex_models import MAJOR_FOREX_PAIRS  # noqa: E402
from app.trading.models import TradingValidationError  # noqa: E402


def _result(status: str, reason: str = "") -> dict[str, object]:
    return {
        "status": status,
        "reason": reason[:120],
        "pair_count": len(MAJOR_FOREX_PAIRS) if status == "READY" else 0,
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def main() -> int:
    load_forex_environment(PROJECT_ROOT)
    settings = ForexDataSettings.from_environment()
    if (
        not settings.enabled
        or settings.primary_provider != "MT5_DEMO"
        or not settings.paper_autopilot_enabled
    ):
        print(json.dumps(_result("NOT_READY", "configuration_blocked")))
        return 2
    requested_at = datetime.now(timezone.utc)
    try:
        quotes, bars = Mt5DemoReadOnlySource(
            symbol_suffix=settings.mt5_symbol_suffix,
        ).fetch_market(MAJOR_FOREX_PAIRS, bar_count=31, now=requested_at)
        ready = mt5_market_snapshot_fresh(
            MAJOR_FOREX_PAIRS,
            quotes,
            bars,
            now=datetime.now(timezone.utc),
        )
    except (OSError, RuntimeError, TradingValidationError) as error:
        print(json.dumps(_result("NOT_READY", str(error))))
        return 2
    result = _result("READY" if ready else "NOT_READY", "" if ready else "stale_market")
    print(json.dumps(result))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

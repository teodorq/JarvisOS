"""Run one explicitly enabled autonomous local Forex PAPER cycle."""

from __future__ import annotations

import argparse
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
from app.market_data.forex_paper_runtime import ForexDemoPaperRuntime  # noqa: E402
from app.trading.forex_activity_journal import ForexPaperActivityJournal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "JARVIS OS: autonomiczny lokalny Forex PAPER bez zlecen brokera."
        )
    )
    parser.add_argument("--cycle-id", default="")
    arguments = parser.parse_args()
    load_forex_environment(PROJECT_ROOT)
    settings = ForexDataSettings.from_environment()
    now = datetime.now(timezone.utc)
    cycle_id = arguments.cycle_id.strip() or (
        "autopaper-" + now.strftime("%Y%m%dT%H%M%SZ")
    )
    activity_history = ForexPaperActivityJournal(PROJECT_ROOT)
    try:
        activity_history.initialize()
    except (OSError, RuntimeError, TimeoutError):
        pass
    result = ForexDemoPaperRuntime(
        PROJECT_ROOT,
        settings=settings,
    ).run_once(cycle_id=cycle_id, now=now)
    result.setdefault("observed_at", now.isoformat())
    try:
        history = activity_history.record(result)
        result["activity_history_status"] = history["status"]
        result["activity_history_events_recorded"] = history["events_recorded"]
    except (OSError, RuntimeError, TimeoutError):
        result["activity_history_status"] = "WRITE_FAILED"
        result["activity_history_events_recorded"] = 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PAPER_CYCLE_COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
